"""Collection health reports absence, partial evidence, and real export timestamps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.archive import export_sources
from agent_sessions.archive_status import status_summary, status_to_dict
from agent_sessions.collection_health import collection_health, index_state
from agent_sessions.config import ArchiveConfig, load_config


def test_empty_and_source_states(tmp_path: Path) -> None:
    (tmp_path / "sources.toml").write_text('''
[[sources]]
name = "off"
kind = "claude"
enabled = false
[[sources]]
name = "missing"
kind = "claude"
roots = ["missing-root"]
[[sources]]
name = "inventory"
kind = "inventory"
[[sources]]
name = "router"
kind = "router_index"
enabled = false
''')
    health = status_to_dict(status_summary(load_config(tmp_path)))["collection"]
    assert health["state"] == "no_sessions"
    assert health["last_successful_export"] is None
    assert health["sources"] == {"off": "disabled", "missing": "roots_missing",
                                 "inventory": "inventory_only", "router": "router_managed"}
    assert health["indexes"][".router-index.jsonl"] == "missing"


def test_router_counts_errors_and_unknown_times(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    artifact = archive / "routed.md"
    artifact.write_text("## user\nQuestion\n## assistant\nAnswer\n")
    config = ArchiveConfig(tmp_path, archive, tmp_path / "raw", ())
    record = {"source": "zai", "source_file": "fixture", "messages": 2,
              "markdown": "archive/routed.md", "metadata": {"session_id": "test"}}
    index = archive / ".router-index.jsonl"
    index.write_text(json.dumps(record) + "\n")
    health = status_summary(config).collection
    assert health["messages"] == 2 and health["sessions"] == 1
    assert health["last_successful_export"] is None  # no source/index mtime guess
    assert health["local_markdown_bytes"] == artifact.stat().st_size
    index.write_text(json.dumps(record) + "\nnot-json\n")
    health = status_summary(config).collection
    assert health["state"] == "attention_required"
    assert health["indexes"][".router-index.jsonl"] == "malformed"
    assert health["sessions"] == 1  # retain the readable partial evidence


def test_artifact_containment_and_timestamp_validation(tmp_path: Path) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    secret = tmp_path / "outside.txt"
    secret.write_text("not archive data")
    health = collection_health(config, [
        {"markdown": "outside.txt", "messages": True, "exported_at": "invalid"},
        {"messages": -1, "exported_at": "2026-09-15T12:00:00"},
        {"messages": 4, "exported_at": "2026-09-15T12:00:00+05:30"},
    ])
    assert health["missing_local_artifacts"] == 3
    assert health["local_markdown_bytes"] == 0
    assert health["sessions_with_unknown_message_count"] == 2
    assert health["last_successful_export"] == "2026-09-15T06:30:00+00:00"
    malformed = collection_health(config, [{"markdown": "archive/bad\x00path"}])
    assert malformed["missing_local_artifacts"] == 1


@pytest.mark.parametrize("contents", ["[]", "{}", "invalid", "\ufffd"])
def test_malformed_index(tmp_path: Path, contents: str) -> None:
    index = tmp_path / "index.jsonl"
    index.write_text(contents, encoding="utf-8")
    assert index_state(index) == "malformed"


def test_unreadable_index(tmp_path: Path) -> None:
    assert index_state(tmp_path) == "unreadable"
    archive = tmp_path / "archive"
    (archive / "index.jsonl").mkdir(parents=True)
    config = ArchiveConfig(tmp_path, archive, tmp_path / "raw", ())
    health = status_summary(config).collection
    assert health["state"] == "attention_required"
    assert health["sessions"] is None and health["messages"] is None
    assert health["counts_complete"] is False


def test_export_records_time_without_changing_it_on_reuse(archive_config: ArchiveConfig) -> None:
    root = archive_config.sources[0].roots[0]
    root.mkdir(parents=True)
    (root / "session.jsonl").write_text(json.dumps({"type": "user", "sessionId": "fixture",
                                                  "message": {"role": "user", "content": "Hello"}}) + "\n")
    export_sources(archive_config)
    first = status_summary(archive_config).collection
    assert first["last_successful_export"] is not None
    export_sources(archive_config)
    assert status_summary(archive_config).collection["last_successful_export"] == first["last_successful_export"]
