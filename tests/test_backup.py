"""Recovery and failure fixtures for independent backup storage."""
from __future__ import annotations

import json
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
)
from agent_sessions.cli import main
from agent_sessions.config import ArchiveConfig, load_config
from agent_sessions.models import Source


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
