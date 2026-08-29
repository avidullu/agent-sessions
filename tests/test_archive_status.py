"""Tests for agent_sessions.archive_status."""

from __future__ import annotations

import os

import pytest

from agent_sessions.archive import export_sources, sha256_file, tail_sha256_file, write_indexes
from agent_sessions.archive_status import (
    archive_status,
    classify_source_origin,
    render_status,
    status_summary,
    status_to_dict,
)
from agent_sessions.config import ArchiveConfig


class TestClassifySourceOrigin:
    # Neutral example usernames — these are pure-function fixtures for the
    # classifier, not environment-dependent; the real auditing user's identity
    # must not appear in test inputs or expected labels.
    def test_windows_user_path(self) -> None:
        origin = classify_source_origin(r"C:\Users\alice\.codex\sessions\a.jsonl")
        assert origin.kind == "windows-user"
        assert origin.label == "C:/Users/alice"

    def test_wsl_unc_path(self) -> None:
        origin = classify_source_origin(r"\\wsl.localhost\Ubuntu\home\alice\.grok\sessions\chat_history.jsonl")
        assert origin.kind == "wsl-user"
        assert origin.label == "Ubuntu:/home/alice"

    def test_posix_home_path(self) -> None:
        origin = classify_source_origin("/home/alice/.claude/projects/session.jsonl")
        assert origin.kind == "posix-home"
        assert origin.label == "/home/alice"

    def test_wsl_mounted_windows_path(self) -> None:
        origin = classify_source_origin("/mnt/c/Users/alice/Projects/session.jsonl")
        assert origin.kind == "wsl-mounted-windows-user"
        assert origin.label == "C:/Users/alice"

    def test_unknown_path(self) -> None:
        origin = classify_source_origin("relative/session.jsonl")
        assert origin.kind == "unknown"
        assert origin.label == "relative/session.jsonl"


class TestStatusSummary:
    def test_reports_new_changed_and_not_visible_records(self, archive_config: ArchiveConfig) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        same = root / "same.jsonl"
        changed = root / "changed.jsonl"
        new_file = root / "new.jsonl"
        same.write_text('{"sessionId":"same"}\n', encoding="utf-8")
        changed.write_text('{"sessionId":"changed"}\n', encoding="utf-8")
        new_file.write_text('{"sessionId":"new"}\n', encoding="utf-8")
        records = [
            {
                "source": "test-claude",
                "kind": "claude",
                "source_file": str(same),
                "sha256": sha256_file(same),
                "messages": 0,
                "markdown": "archive/test-claude/same.md",
                "metadata": {},
            },
            {
                "source": "test-claude",
                "kind": "claude",
                "source_file": str(changed),
                "sha256": "old-digest",
                "messages": 0,
                "markdown": "archive/test-claude/changed.md",
                "metadata": {},
            },
            {
                "source": "remote-claude",
                "kind": "claude",
                "source_file": r"C:\Users\other\.claude\projects\session.jsonl",
                "sha256": "remote-digest",
                "messages": 1,
                "markdown": "archive/remote-claude/session.md",
                "metadata": {},
            },
        ]
        write_indexes(archive_config, records)

        summary = status_summary(archive_config)

        assert summary.visible_files == 3
        assert summary.new_files == 1
        assert summary.changed_files == 1
        assert summary.not_visible_records == 1
        assert summary.source_counts["remote-claude"] == 1
        assert any(origin.startswith("windows-user:") for origin in summary.origin_counts)

    def test_size_mtime_short_circuit_skips_hashing(self, archive_config: ArchiveConfig, monkeypatch: pytest.MonkeyPatch) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        same = root / "same.jsonl"
        same.write_text('{"sessionId":"same"}\n', encoding="utf-8")
        stat_result = same.stat()
        write_indexes(
            archive_config,
            [
                {
                    "source": "test-claude",
                    "kind": "claude",
                    "source_file": str(same),
                    "sha256": "stale-digest-should-not-be-read",
                    "size": stat_result.st_size,
                    "mtime": stat_result.st_mtime,
                    "messages": 0,
                    "markdown": "archive/test-claude/same.md",
                    "metadata": {},
                }
            ],
        )

        def _boom(_path: object) -> str:
            raise AssertionError("sha256_file must not be called when size+mtime match")

        monkeypatch.setattr("agent_sessions.archive_status.sha256_file", _boom)
        summary = status_summary(archive_config)
        assert summary.visible_files == 1
        assert summary.new_files == 0
        assert summary.changed_files == 0

    def test_tail_hash_detects_same_size_mtime_change(self, archive_config: ArchiveConfig) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        changed = root / "changed.jsonl"
        changed.write_text('{"sessionId":"a"}\n', encoding="utf-8")
        stat_result = changed.stat()
        write_indexes(
            archive_config,
            [
                {
                    "source": "test-claude",
                    "kind": "claude",
                    "source_file": str(changed),
                    "sha256": sha256_file(changed),
                    "tail_sha256": tail_sha256_file(changed),
                    "size": stat_result.st_size,
                    "mtime": stat_result.st_mtime,
                    "messages": 0,
                    "markdown": "archive/test-claude/changed.md",
                    "metadata": {},
                }
            ],
        )

        changed.write_text('{"sessionId":"b"}\n', encoding="utf-8")
        os.utime(changed, (stat_result.st_mtime, stat_result.st_mtime))

        summary = status_summary(archive_config)
        assert summary.changed_files == 1

    def test_deduplicated_alias_is_not_reported_as_new(self, archive_config: ArchiveConfig) -> None:
        root = archive_config.sources[0].roots[0]
        first = root / "first" / "session.jsonl"
        alias = root / "second" / "session-copy.jsonl"
        first.parent.mkdir(parents=True)
        alias.parent.mkdir(parents=True)
        content = '{"sessionId":"shared-session","messages":[]}\n'
        first.write_text(content, encoding="utf-8")
        alias.write_text(content, encoding="utf-8")

        result = export_sources(archive_config)
        summary = status_summary(archive_config)

        assert result.exported == 2
        assert summary.visible_files == 2
        assert summary.indexed_records == 1
        assert summary.new_files == 0
        assert summary.changed_files == 0

    def test_distinct_size_new_file_does_not_hash(self, archive_config: ArchiveConfig, monkeypatch: pytest.MonkeyPatch) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        indexed = root / "indexed.jsonl"
        indexed.write_text('{"sessionId":"indexed"}\n', encoding="utf-8")
        export_sources(archive_config)
        new_file = root / "new.jsonl"
        new_file.write_text('{"sessionId":"new-and-a-distinct-size","messages":[]}\n', encoding="utf-8")

        def _boom(_path: object) -> str:
            raise AssertionError("sha256_file must not be called without a same-size alias candidate")

        monkeypatch.setattr("agent_sessions.archive_status.sha256_file", _boom)
        summary = status_summary(archive_config)

        assert summary.new_files == 1


    def test_same_size_different_tail_does_not_hash(
        self, archive_config: ArchiveConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        indexed = root / "indexed.jsonl"
        new_file = root / "new.jsonl"
        indexed_body = '{"sessionId":"indexed","pad":"' + ("A" * 40) + '"}' + "\n"
        new_body = '{"sessionId":"newfile","pad":"' + ("B" * 40) + '"}' + "\n"
        assert len(indexed_body) == len(new_body)
        indexed.write_text(indexed_body, encoding="utf-8")
        export_sources(archive_config)
        new_file.write_text(new_body, encoding="utf-8")

        def _boom(_path: object) -> str:
            raise AssertionError("sha256_file must not run when tails differ")

        monkeypatch.setattr("agent_sessions.archive_status.sha256_file", _boom)
        summary = status_summary(archive_config)

        assert summary.new_files == 1

    def test_byte_identical_pair_without_session_id_is_new(self, archive_config: ArchiveConfig) -> None:
        root = archive_config.sources[0].roots[0]
        first = root / "first" / "session.jsonl"
        alias = root / "second" / "session-copy.jsonl"
        first.parent.mkdir(parents=True)
        alias.parent.mkdir(parents=True)
        content = '{"messages":[]}' + "\n"
        first.write_text(content, encoding="utf-8")
        export_sources(archive_config)
        alias.write_text(content, encoding="utf-8")

        summary = status_summary(archive_config)

        assert summary.visible_files == 2
        assert summary.indexed_records == 1
        assert summary.new_files == 1

    def test_render_status(self, archive_config: ArchiveConfig) -> None:
        write_indexes(
            archive_config,
            [
                {
                    "source": "remote-claude",
                    "kind": "claude",
                    "source_file": r"C:\Users\other\.claude\projects\session.jsonl",
                    "sha256": "remote-digest",
                    "messages": 1,
                    "markdown": "archive/remote-claude/session.md",
                    "metadata": {},
                },
            ],
        )
        summary = status_summary(archive_config)
        text = render_status(summary)
        assert "# Archive Status" in text
        assert "Indexed records" in text
        assert "remote-claude" in text

    def test_status_to_dict(self, archive_config: ArchiveConfig) -> None:
        write_indexes(archive_config, [])
        payload = status_to_dict(status_summary(archive_config))
        assert payload["indexed_records"] == 0
        assert "origin_counts" in payload

    def test_archive_status_json(self, archive_config: ArchiveConfig, capsys: pytest.CaptureFixture[str]) -> None:
        write_indexes(archive_config, [])
        result = archive_status(archive_config, as_json=True)
        out = capsys.readouterr().out
        assert result == 0
        assert '"indexed_records": 0' in out

    def test_archive_status_text(self, archive_config: ArchiveConfig, capsys: pytest.CaptureFixture[str]) -> None:
        write_indexes(archive_config, [])
        result = archive_status(archive_config)
        out = capsys.readouterr().out
        assert result == 0
        assert "# Archive Status" in out

    def test_skips_sources_without_extractors(self, multi_source_config: ArchiveConfig) -> None:
        write_indexes(multi_source_config, [])
        summary = status_summary(multi_source_config, selected=["inventory"])
        text = render_status(summary)
        assert summary.skipped_sources == ("test-inventory (inventory)",)
        assert "test-inventory" in text
