"""Statistics use record/session/byte definitions, not accidental row counts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_sessions.archive_stats import archive_statistics, backup_metrics, catalog_metrics, render_statistics
from agent_sessions.backup import backup, initialize, object_path, snapshots
from agent_sessions.cli import main
from agent_sessions.config import ArchiveConfig
from agent_sessions.models import Source


def test_definitions_and_distributions() -> None:
    rows: list[dict[str, Any]] = [
        {'kind': 'codex', 'source': 'a', 'metadata': {'session_id': 'one'}, 'size': 100, 'messages': 2, 'mtime': 0},
        {'kind': 'codex', 'source': 'b', 'metadata': {'session_id': 'one'}, 'size': 200, 'messages': 3, 'mtime': 0},
        {'kind': 'claude', 'source': 'c', 'metadata': {'session_id': 'one'}, 'size': 300, 'messages': 1},
        {'source': 'unknown'},
    ]
    report = catalog_metrics(rows)
    assert report['catalog_records'] == 4
    assert report['distinct_identified_sessions'] == 2
    assert report['records_without_session_id'] == 1
    assert report['messages'] == 6
    assert report['record_source_bytes'] == 600
    assert report['records_without_size'] == 1
    assert report['source_size_percentiles_bytes'] == {'p50': 200, 'p90': 300, 'p99': 300, 'p100': 300}
    assert report['source_modified_months_utc'] == {'1970-01': 2, 'unknown': 2}
    assert catalog_metrics([])['source_size_percentiles_bytes']['p50'] is None


@pytest.mark.parametrize('compression', ['gzip', 'none'])
def test_backup_metrics_and_coverage(tmp_path: Path, compression: str) -> None:
    repo = tmp_path / 'repo'
    archive = repo / 'archive'
    archive.mkdir(parents=True)
    raw = repo / 'raw'
    raw.mkdir()
    transcript = archive / 'example.md'
    transcript.write_text('an archived conversation\n' * 100)
    (raw / 'saved.gz').write_bytes(b'pre-existing backup' * 100)
    rows = [
        {'kind': 'codex', 'source': 'a', 'metadata': {'session_id': 'one'}, 'sha256': '1' * 64,
         'markdown': 'archive/example.md', 'raw': 'raw/saved.gz', 'size': 500, 'messages': 2},
        {'kind': 'claude', 'source': 'b', 'metadata': {'session_id': 'two'}, 'sha256': '2' * 64,
         'markdown': 'archive/missing.md'},
    ]
    (archive / 'index.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    config = ArchiveConfig(repo, archive, raw, (), backup_dir=tmp_path / 'vault')
    root = tmp_path / 'vault'
    initialize(root, compression)
    backup(config, root, 'example')
    backup(config, root, 'example')
    metrics = backup_metrics(root)
    assert metrics['snapshots'] == 2
    assert metrics['file_versions'] == 3
    assert metrics['unique_objects'] == 3
    assert metrics['catalog_history']['catalog_records'] == 2
    assert metrics['catalog_records_with_raw_or_original'] == 1
    assert metrics['catalog_records_without_preserved_transcript'] == 1
    assert metrics['deduplication_saved_fraction'] == 0
    if compression == 'gzip':
        assert metrics['compression_saved_fraction'] > .5
    else:
        assert metrics['compression_saved_fraction'] == 0
    report = archive_statistics(config, root)
    assert report['local_artifacts']['records_missing_markdown'] == 1
    rendered = render_statistics(report)
    assert 'Compression (' in rendered and 'Source modification month' in rendered
    assert '2' in rendered
    raw_entry = next(e for _, s in snapshots(root) for e in s['files'] if e['category'] == 'raw')
    object_path(root, raw_entry['sha256']).unlink()
    assert backup_metrics(root)['missing_objects'] == 1
    assert backup_metrics(root)['catalog_records_with_raw_or_original'] == 0
    (repo / 'sources.toml').write_text('[archive]\n')
    report_file = tmp_path / 'stats.json'
    assert main(['--repo-root', str(repo), 'stats', '--json', '--output', str(report_file)]) == 0
    assert json.loads(report_file.read_text())['catalog']['catalog_records'] == 2
    (archive / 'index.jsonl').unlink()
    (repo / 'sources.toml').unlink()
    assert main(['--repo-root', str(repo), 'stats', '--destination', str(root),
                 '--json', '--output', str(report_file)]) == 0
    recovered = json.loads(report_file.read_text())
    assert recovered['catalog']['catalog_records'] == 2
    assert recovered['catalog_scope'].startswith('all retained backup')


def test_dedup_savings_separate_from_compression(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    logs = tmp_path / 'logs'
    logs.mkdir()
    for name in ['one.jsonl', 'two.jsonl']:
        (logs / name).write_text('duplicate bytes\n' * 100)
    config = ArchiveConfig(repo, repo / 'archive', repo / 'raw',
                           (Source('test', 'inventory', (logs,), '*.jsonl'),))
    root = tmp_path / 'vault'
    initialize(root)
    backup(config, root)
    stats = backup_metrics(root)
    assert stats['unique_objects'] == 1 and stats['file_versions'] == 2
    assert stats['deduplication_saved_fraction'] == .5
    assert stats['compression_saved_fraction'] > .5
    assert '0' in render_statistics(archive_statistics(config))


def test_windows_catalog_in_portable_backup(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    archive = repo / 'archive'
    archive.mkdir(parents=True)
    (archive / 'index.jsonl').write_text(json.dumps({'kind': 'codex', 'metadata': {'session_id': 'one'}}) + '\n')
    config = ArchiveConfig(repo, archive, repo / 'raw', ())
    root = tmp_path / 'vault'
    initialize(root)
    backup(config, root)
    path, snapshot = list(snapshots(root))[0]
    snapshot['files'][0]['path'] = 'E:\\example\\archive\\index.jsonl'
    path.write_text(json.dumps(snapshot))
    assert backup_metrics(root)['catalog_history']['catalog_records'] == 1
