"""Tests for report-only baseline handoff auditing."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from agent_sessions.baseline_handoffs import (
    baseline_handoffs_audit,
    build_handoff_audit,
    handoff_sections,
    has_start_here_pointer,
    render_handoff_audit,
)
from agent_sessions.config import ArchiveConfig


def _config(repo_root: Path) -> ArchiveConfig:
    return ArchiveConfig(
        repo_root=repo_root,
        archive_dir=repo_root / "archive",
        raw_dir=repo_root / "raw",
        sources=(),
    )


def _handoff_text() -> str:
    return """# Session Handoff

## You Are Here

Working on baseline handoff audit.

## Next Steps / Open Threads

- Keep K2 report-only.

## Ramp-Up Kit

- docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md

## Key Decisions

- K6 owns persistent indexes.
"""


class TestHandoffParsing:
    def test_detects_standard_sections(self) -> None:
        sections = handoff_sections(_handoff_text())
        assert sections == (
            "You Are Here",
            "Next Steps / Open Threads",
            "Ramp-Up Kit",
            "Key Decisions",
        )

    def test_detects_memory_start_here_pointer(self) -> None:
        text = '- ▶ Start here: `memory/session-handoff.md`\n'
        assert has_start_here_pointer(text) is True


class TestBuildHandoffAudit:
    def test_analyzes_repo_handoff_and_memory_pointer(self, repo_root: Path) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        (repo_root / "MEMORY.md").write_text(
            '- ▶ Start here: `memory/session-handoff.md`\n',
            encoding="utf-8",
        )
        audit = build_handoff_audit(
            _config(repo_root),
            now=dt.datetime(2026, 7, 7, tzinfo=dt.timezone.utc),
        )
        paths = {item.path for item in audit.repo_files}
        assert "SESSION_HANDOFF.md" in paths
        assert "MEMORY.md" in paths
        assert audit.missing_expected_paths == ()

    def test_flags_missing_memory_start_here_pointer(self, repo_root: Path) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        (repo_root / "MEMORY.md").write_text("# Memory\n\nNo pointer yet.\n", encoding="utf-8")
        audit = build_handoff_audit(
            _config(repo_root),
            now=dt.datetime(2026, 7, 7, tzinfo=dt.timezone.utc),
        )
        report = render_handoff_audit(audit)
        assert "MEMORY.md start-here pointer" in report

    def test_scans_archive_handoff_candidates(self, repo_root: Path) -> None:
        archive_dir = repo_root / "archive"
        markdown_dir = archive_dir / "codex"
        markdown_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = markdown_dir / "session.md"
        markdown_path.write_text(_handoff_text(), encoding="utf-8")
        (archive_dir / "index.jsonl").write_text(
            json.dumps(
                {
                    "source": "codex",
                    "kind": "codex",
                    "source_file": "/fake/session.jsonl",
                    "sha256": "abc",
                    "messages": 3,
                    "markdown": "archive/codex/session.md",
                    "metadata": {"session_id": "s1", "project": "%2FC%3A%2FProject"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        audit = build_handoff_audit(
            _config(repo_root),
            now=dt.datetime(2026, 7, 7, tzinfo=dt.timezone.utc),
        )
        assert audit.archive_records_scanned == 1
        assert len(audit.archive_hits) == 1
        assert audit.archive_hits[0].session_id == "s1"


class TestBaselineHandoffsAudit:
    def test_writes_only_audit_file(self, repo_root: Path) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        result = baseline_handoffs_audit(_config(repo_root))
        assert result == 0
        assert (repo_root / "baseline" / "handoffs" / "audit.md").exists()
        assert not (repo_root / "baseline" / "handoffs" / "index.jsonl").exists()
        assert not list((repo_root / "baseline" / "proposals").glob("*.json"))

    def test_dry_run_does_not_write(self, repo_root: Path, capsys) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        result = baseline_handoffs_audit(_config(repo_root), dry_run=True)
        assert result == 0
        assert "Would write" in capsys.readouterr().out
        assert not (repo_root / "baseline" / "handoffs" / "audit.md").exists()
