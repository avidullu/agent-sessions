"""Tests for router index (.router-index.jsonl) ingestion."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.archive import read_router_index_records, merge_index_records, ROUTER_INDEX_FILENAME
from agent_sessions.config import ArchiveConfig


def test_read_router_index_returns_empty_when_missing(tmp_path: Path):
    """Returns empty list when .router-index.jsonl doesn't exist."""
    config = ArchiveConfig(
        repo_root=tmp_path,
        archive_dir=tmp_path / "archive",
        raw_dir=tmp_path / "raw",
        sources=(),
    )
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    records = read_router_index_records(config)
    assert records == []


def test_read_router_index_parses_valid_records(tmp_path: Path):
    """Parses valid JSONL entries from .router-index.jsonl."""
    config = ArchiveConfig(
        repo_root=tmp_path,
        archive_dir=tmp_path / "archive",
        raw_dir=tmp_path / "raw",
        sources=(),
    )
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    router_index = config.archive_dir / ROUTER_INDEX_FILENAME
    router_index.write_text(
        json.dumps({"source": "copilot-vscode", "kind": "copilot_chat", "source_file": "/test/main.jsonl",
                     "sha256": "abc123", "size": 1000, "mtime": 1.0, "messages": 42,
                     "markdown": "archive/copilot-vscode/session.md",
                     "metadata": {"session_id": "test-session-1"}})
        + "\n"
        + json.dumps({"source": "deepseek-vscode", "kind": "deepseek_request_dump", "source_file": "/test/input.json",
                       "sha256": "def456", "size": 2000, "mtime": 2.0, "messages": 10,
                       "markdown": "archive/deepseek-vscode/session.md",
                       "metadata": {"session_id": "test-session-2"}})
        + "\n",
        encoding="utf-8",
    )
    records = read_router_index_records(config)
    assert len(records) == 2
    assert records[0]["source"] == "copilot-vscode"
    assert records[0]["messages"] == 42
    assert records[1]["source"] == "deepseek-vscode"
    assert records[1]["metadata"]["session_id"] == "test-session-2"


def test_read_router_index_handles_malformed_file(tmp_path: Path):
    """Gracefully handles malformed .router-index.jsonl."""
    config = ArchiveConfig(
        repo_root=tmp_path,
        archive_dir=tmp_path / "archive",
        raw_dir=tmp_path / "raw",
        sources=(),
    )
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    router_index = config.archive_dir / ROUTER_INDEX_FILENAME
    router_index.write_text("not valid json\n", encoding="utf-8")
    # Should not raise; should return empty list
    records = read_router_index_records(config)
    assert records == []


def test_merge_index_records_includes_router_entries(tmp_path: Path):
    """Router records are merged into the main index without duplication."""
    existing = [
        {"source": "codex-windows", "kind": "codex", "source_file": "/codex/session.jsonl",
         "sha256": "aaa", "size": 500, "mtime": 1.0, "messages": 5,
         "markdown": "archive/codex-windows/session.md",
         "metadata": {"session_id": "codex-1"}},
    ]
    router = [
        {"source": "copilot-vscode", "kind": "copilot_chat", "source_file": "/copilot/main.jsonl",
         "sha256": "bbb", "size": 1000, "mtime": 2.0, "messages": 42,
         "markdown": "archive/copilot-vscode/session.md",
         "metadata": {"session_id": "copilot-1"}},
    ]
    merged = merge_index_records(existing, router)
    assert len(merged) == 2
    sources = {r["source"] for r in merged}
    assert "codex-windows" in sources
    assert "copilot-vscode" in sources


def test_merge_index_records_deduplicates_by_session_id(tmp_path: Path):
    """Router records don't duplicate existing records with the same session_id."""
    existing = [
        {"source": "copilot-vscode", "kind": "copilot_chat", "source_file": "/old/path.jsonl",
         "sha256": "oldhash", "size": 1000, "mtime": 1.0, "messages": 42,
         "markdown": "archive/copilot-vscode/session.md",
         "metadata": {"session_id": "same-session"}},
    ]
    router = [
        {"source": "copilot-vscode", "kind": "copilot_chat", "source_file": "/new/path.jsonl",
         "sha256": "newhash", "size": 1000, "mtime": 2.0, "messages": 42,
         "markdown": "archive/copilot-vscode/session.md",
         "metadata": {"session_id": "same-session"}},
    ]
    merged = merge_index_records(existing, router)
    # merge_index_records uses index_identity_key which is session_id-based
    # When session_id matches, the later record supersedes
    assert len(merged) == 1
    assert merged[0]["sha256"] == "newhash"  # Router record supersedes existing
