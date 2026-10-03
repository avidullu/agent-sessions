"""Recovery and failure fixtures for independent backup storage."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sessions.backup import (
    backup,
    destination,
    initialize,
    object_path,
    restore,
    safe_path,
    snapshots,
    store_file,
    verify,
    writer_lock,
)
from agent_sessions.cli import main
from agent_sessions.config import ArchiveConfig, load_config
from agent_sessions.models import Source
from agent_sessions.path_templates import PathTemplateContext


@pytest.fixture
def configured(tmp_path: Path) -> ArchiveConfig:
    repo = tmp_path / 'repo'
    repo.mkdir()
    source = tmp_path / 'agent-logs'
    source.mkdir()
    (source / 'session.jsonl').write_text('hello log\n' * 1000)
    return ArchiveConfig(repo, repo / 'archive', repo / 'raw',
                         (Source('example', 'inventory', (source,), '**/*.jsonl'),),
                         backup_dir=tmp_path / 'external-vault')


@pytest.mark.parametrize('compression', ['gzip', 'none'])
def test_preserves_versions_and_restores_without_source(configured: ArchiveConfig, compression: str) -> None:
    root = destination(configured)
    initialize(root, compression)
    first = backup(configured, root, 'test-host')
    with patch('agent_sessions.backup.compressed_writer', side_effect=AssertionError('unexpected recompression')):
        second = backup(configured, root, 'test-host')
    assert second['new_objects'] == 0
    source = configured.sources[0].roots[0] / 'session.jsonl'
    source.write_text('changed\n')
    assert backup(configured, root, 'test-host')['new_objects'] == 1
    source.unlink()
    assert backup(configured, root, 'test-host')['files'] == 0
    assert verify(root) == {'snapshots': 4, 'objects_checked': 2, 'failures': [], 'ok': True}
    output = root.parent / 'restore'
    assert restore(root, first['snapshot'], output) == 1
    mapping = json.loads((output / 'restore-map.json').read_text())
    assert (output / mapping['files'][0]['restored_file']).read_text() == 'hello log\n' * 1000
    with pytest.raises(FileExistsError):
        restore(root, first['snapshot'], output)


def test_history_raw_and_inventory_included(configured: ArchiveConfig) -> None:
    configured.archive_dir.mkdir()
    configured.raw_dir.mkdir()
    (configured.archive_dir / 'old.md').write_text('old rendered session')
    (configured.raw_dir / 'old.jsonl.gz').write_bytes(b'old raw backup')
    root = destination(configured)
    initialize(root)
    result = backup(configured, root)
    assert result['files'] == 3
    assert {e['category'] for _, s in snapshots(root) for e in s['files']} == {'source', 'raw', 'archive'}
    with pytest.raises(ValueError, match='lock'):
        (root / '.write.lock').write_text('active')
        backup(configured, root)


def test_missing_destination_and_overlap_fail_closed(configured: ArchiveConfig) -> None:
    root = destination(configured)
    with pytest.raises(ValueError, match='unavailable'):
        backup(configured, root)
    assert not root.exists()
    with pytest.raises(ValueError, match='outside'):
        destination(configured, configured.repo_root / 'backup')
    with pytest.raises(ValueError, match='outside'):
        destination(configured, configured.sources[0].roots[0] / 'backup')
    with pytest.raises(ValueError, match='Set'):
        destination(replace(configured, backup_dir=None))
    with pytest.raises(ValueError, match='parent'):
        initialize(root / 'missing' / 'vault')
    with pytest.raises(ValueError, match='Compression'):
        initialize(root, 'bad')
    root.mkdir()
    (root / 'unrelated').touch()
    with pytest.raises(ValueError, match='empty'):
        initialize(root)


@pytest.mark.parametrize('compression', ['gzip', 'none'])
def test_corruption_is_visible(configured: ArchiveConfig, compression: str) -> None:
    root = destination(configured)
    initialize(root, compression)
    result = backup(configured, root)
    entry = list(snapshots(root))[0][1]['files'][0]
    obj = object_path(root, entry['sha256'])
    obj.write_bytes(b'corrupt')
    assert verify(root)['ok'] is False
    with pytest.raises((ValueError, OSError)):
        backup(configured, root)
    assert len(list(snapshots(root))) == 1
    obj.unlink()
    assert verify(root)['ok'] is False
    with pytest.raises(ValueError, match='filename'):
        restore(root, '../bad', root.parent / 'out')
    with pytest.raises(ValueError, match='not found'):
        restore(root, 'absent.json', root.parent / 'out')
    with pytest.raises(ValueError, match='outside'):
        restore(root, result['snapshot'], root / 'out')


def test_failed_copy_does_not_publish_snapshot(configured: ArchiveConfig) -> None:
    root = destination(configured)
    initialize(root)
    with patch('agent_sessions.backup.os.fsync', side_effect=OSError('disk full')):
        with pytest.raises(OSError, match='disk full'):
            backup(configured, root)
    assert list(snapshots(root)) == []
    assert not (root / '.write.lock').exists()
    assert not list((root / 'objects').glob('.pending-*'))


def test_changing_source_fails_without_snapshot(configured: ArchiveConfig) -> None:
    root = destination(configured)
    initialize(root)
    source = configured.sources[0].roots[0] / 'session.jsonl'
    original_stat = Path.stat
    calls = 0

    def changing_stat(path: Path, **kwargs: bool) -> object:
        nonlocal calls
        if path == source:
            calls += 1
            if calls % 2 == 0:
                with source.open('a') as stream:
                    stream.write('append')
        return original_stat(path, **kwargs)

    with patch.object(Path, 'stat', changing_stat):
        with pytest.raises(ValueError, match='kept changing'):
            store_file(root, source, set())
    assert not list((root / 'snapshots').iterdir())


@pytest.mark.skipif(__import__('os').name == 'nt', reason='Windows symlink privilege varies')
def test_symlink_and_malicious_manifest_fail(configured: ArchiveConfig) -> None:
    root = destination(configured)
    initialize(root)
    other = root.parent / 'elsewhere'
    other.mkdir()
    (root / 'escape').symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        safe_path(root, 'escape/file')
    with pytest.raises(ValueError, match='digest'):
        object_path(root, '../bad')
    with pytest.raises(ValueError, match='Invalid snapshot'):
        (root / 'snapshots/bad.json').write_text('{}')
        list(snapshots(root))


def test_config_and_cli_recovery(configured: ArchiveConfig, capsys: pytest.CaptureFixture[str]) -> None:
    root = destination(configured)
    config_file = configured.repo_root / 'sources.toml'
    config_file.write_text('[backup]\ndirectory = ' + json.dumps(str(root)) + '\nmachine = "fixture"\non_export = true\n')
    loaded = load_config(configured.repo_root)
    assert loaded.backup_dir == root and loaded.backup_on_export and loaded.backup_machine == 'fixture'
    prefix = ['--repo-root', str(configured.repo_root)]
    assert main(prefix + ['backup', 'init']) == 0
    assert main(prefix + ['backup', 'run']) == 0
    assert main(prefix + ['backup', 'verify']) == 0
    config_file.unlink()
    assert main(prefix + ['backup', 'verify', '--destination', str(root)]) == 0
    assert main(prefix + ['backup', 'verify', '--destination', str(root / 'absent')]) == 2
    assert 'unavailable' in capsys.readouterr().err


def test_export_preflights_missing_backup(configured: ArchiveConfig) -> None:
    config_file = configured.repo_root / 'sources.toml'
    config_file.write_text('[backup]\ndirectory = ' + json.dumps(str(configured.backup_dir)) + '\non_export = true\n')
    prefix = ['--repo-root', str(configured.repo_root)]
    assert main(prefix + ['export', '--all']) == 2
    assert not configured.archive_dir.exists()
    initialize(destination(configured))
    assert main(prefix + ['export', '--all']) == 0
    assert len(list(snapshots(destination(configured)))) == 1


def test_broken_deflate_is_reported(configured: ArchiveConfig) -> None:
    root = destination(configured)
    initialize(root)
    backup(configured, root)
    entry = list(snapshots(root))[0][1]['files'][0]
    obj = object_path(root, entry['sha256'])
    data = obj.read_bytes()
    obj.write_bytes(data[:10] + b'\xff' * 8 + data[-8:])
    assert verify(root)['ok'] is False


def test_initialization_cannot_change_compression(configured: ArchiveConfig) -> None:
    root = destination(configured)
    initialize(root, 'none')
    initialize(root, 'none')
    with pytest.raises(ValueError, match='different compression'):
        initialize(root, 'gzip')


def test_backup_config_preserves_disabled_sources(configured: ArchiveConfig) -> None:
    config_file = configured.repo_root / 'sources.toml'
    config_file.write_text(
        '[backup]\ndirectory = ' + json.dumps(str(configured.backup_dir)) + '\non_export = true\n'
        '[[sources]]\nname = "disabled-fixture"\nkind = "inventory"\nenabled = false\n'
        'roots = [' + json.dumps(str(configured.sources[0].roots[0])) + ']\n', encoding='utf-8',
    )
    loaded = load_config(configured.repo_root)
    assert loaded.sources == ()
    assert loaded.disabled_sources[0].name == 'disabled-fixture'
    initialize(destination(loaded))
    assert backup(loaded, destination(loaded))['files'] == 0


def test_backup_bad_config_uses_safe_onboarding_error(
    configured: ArchiveConfig, capsys: pytest.CaptureFixture[str],
) -> None:
    (configured.repo_root / 'sources.toml').write_text('private-value = [invalid', encoding='utf-8')
    assert main(['--repo-root', str(configured.repo_root), 'backup', 'run']) == 2
    error = capsys.readouterr().err
    assert 'TOMLDecodeError' in error and 'private-value' not in error


@pytest.mark.parametrize('damage', [
    'utf8', 'json', 'scalar', 'files', 'entry', 'digest', 'bytes', 'negative', 'boolean', 'machine',
])
def test_damaged_snapshot_does_not_block_healthy_recovery(configured: ArchiveConfig, damage: str) -> None:
    root = destination(configured)
    initialize(root)
    result = backup(configured, root)
    _, manifest = next(snapshots(root))
    damaged = root / 'snapshots/000-damaged.json'
    if damage == 'utf8':
        damaged.write_bytes(b'\xff')
    elif damage == 'json':
        damaged.write_text('{')
    elif damage == 'scalar':
        damaged.write_text('null')
    else:
        if damage == 'files':
            manifest['files'] = None
        elif damage == 'entry':
            manifest['files'] = [None]
        elif damage == 'digest':
            del manifest['files'][0]['sha256']
        elif damage == 'bytes':
            del manifest['files'][0]['bytes']
        elif damage == 'negative':
            manifest['files'][0]['bytes'] = -1
        elif damage == 'boolean':
            manifest['files'][0]['bytes'] = True
        else:
            manifest['machine'] = []
        damaged.write_text(json.dumps(manifest))
    report = verify(root)
    assert report == {'snapshots': 2, 'objects_checked': 1,
                      'failures': ['Invalid snapshot: 000-damaged.json'], 'ok': False}
    assert restore(root, result['snapshot'], root.parent / 'restored') == 1
    with pytest.raises(ValueError, match='Invalid snapshot'):
        restore(root, damaged.name, root.parent / 'invalid-output')
    assert not (root.parent / 'invalid-output').exists()


def test_unreadable_snapshot_is_reported(configured: ArchiveConfig) -> None:
    root = destination(configured)
    initialize(root)
    result = backup(configured, root)
    damaged = root / 'snapshots/unreadable.json'
    damaged.write_text('{}')
    read_text = Path.read_text

    def read(path: Path, encoding: str | None = None) -> str:
        if path == damaged:
            raise PermissionError
        return read_text(path, encoding=encoding)

    with patch.object(Path, 'read_text', read):
        assert verify(root)['failures'] == ['Invalid snapshot: unreadable.json']
        assert restore(root, result['snapshot'], root.parent / 'restored') == 1


@pytest.mark.parametrize('compression', ['gzip', 'none'])
@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_restore_continues_after_object_failure(
    configured: ArchiveConfig, compression: str, damage: str, capsys: pytest.CaptureFixture[str],
) -> None:
    (configured.sources[0].roots[0] / 'z-last.jsonl').write_text('recover me\n')
    root = destination(configured)
    initialize(root, compression)
    result = backup(configured, root)
    _, manifest = next(snapshots(root))
    first = manifest['files'][0]
    expected = Path(manifest['files'][1]['path']).read_text()
    obj = object_path(root, first['sha256'])
    if damage == 'missing':
        obj.unlink()
    else:
        obj.write_bytes(b'corrupt')
    output = root.parent / 'partial-restore'
    assert main(['--repo-root', str(configured.repo_root), 'backup', 'restore', '--destination', str(root),
                 '--snapshot', result['snapshot'], '--output', str(output)]) == 2
    assert '1 files restored, 1 failed' in capsys.readouterr().err
    mapping = json.loads((output / 'restore-map.json').read_text())
    assert mapping['complete'] is False
    assert mapping['failures'][0]['sha256'] == first['sha256']
    assert len(mapping['files']) == len(mapping['failures']) == 1
    restored_file = output / mapping['files'][0]['restored_file']
    assert restored_file.read_text() == expected
    assert set(output.iterdir()) == {output / 'restore-map.json', restored_file}


@pytest.mark.skipif(os.name == 'nt', reason='Windows prevents unlinking an open lock')
@pytest.mark.parametrize('replacement', [False, True])
def test_writer_cleanup_preserves_replacement_lock(configured: ArchiveConfig, replacement: bool) -> None:
    root = destination(configured)
    initialize(root)
    lock = root / '.write.lock'
    with pytest.raises(RuntimeError, match='writer failed'), writer_lock(root):
        assert 'pid=' in lock.read_text()
        lock.unlink()
        if replacement:
            lock.write_text('successor lock')
        raise RuntimeError('writer failed')
    assert lock.exists() is replacement
    if replacement:
        assert lock.read_text() == 'successor lock'


@pytest.mark.parametrize('template', ['{home}/vault', '$BACKUP_TEST_ROOT/vault', '../vault'])
def test_backup_directory_expands_templates(
    configured: ArchiveConfig, monkeypatch: pytest.MonkeyPatch, template: str,
) -> None:
    base = configured.repo_root.parent
    monkeypatch.setenv('BACKUP_TEST_ROOT', str(base))
    (configured.repo_root / 'sources.toml').write_text('[backup]\ndirectory = ' + json.dumps(template))
    with patch.object(PathTemplateContext, 'from_environment', return_value=PathTemplateContext({'home': str(base)})):
        assert destination(load_config(configured.repo_root)) == base / 'vault'


@pytest.mark.parametrize('settings', [
    'backup = 42', '[backup]\ndirectory = 42', '[backup]\ndirectory = false',
    '[backup]\ndirectory = []', '[backup]\ndirectory = { private = "secret" }',
    '[backup]\ndirectory = ""', '[backup]\ndirectory = "{private-value}/secret"',
])
def test_invalid_backup_config_is_safe_cli_error(
    configured: ArchiveConfig, capsys: pytest.CaptureFixture[str], settings: str,
) -> None:
    (configured.repo_root / 'sources.toml').write_text(settings)
    assert main(['--repo-root', str(configured.repo_root), 'backup', 'run']) == 2
    error = capsys.readouterr().err
    assert 'ValueError' in error and 'private' not in error and 'secret' not in error
