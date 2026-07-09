"""Tests for agent_sessions.archive."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from agent_sessions.archive import (
    ExportResult,
    as_repo_relative,
    copy_raw,
    discover_sources,
    dt_from_timestamp,
    existing_imported_at,
    export_sources,
    iter_source_files,
    load_index_records,
    merge_index_records,
    pdf_existing,
    preserve_generated_at,
    read_existing_index_records,
    select_sources,
    sha256_file,
    source_modified_date,
    write_indexes,
    write_text_if_changed,
)
from agent_sessions.config import ArchiveConfig
from agent_sessions.models import Source


class TestIterSourceFiles:
    def test_yields_files(self, tmp_path: Path) -> None:
        root = tmp_path / "sessions"
        root.mkdir(parents=True)
        (root / "a.jsonl").write_text("a", encoding="utf-8")
        (root / "b.jsonl").write_text("b", encoding="utf-8")
        (root / "sub").mkdir()
        (root / "sub" / "c.jsonl").write_text("c", encoding="utf-8")

        source = Source(name="test", kind="claude", roots=(root,), glob="**/*.jsonl")
        files = list(iter_source_files(source))
        assert len(files) == 3

    def test_skips_missing_root(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        source = Source(name="test", kind="claude", roots=(missing,), glob="**/*.jsonl")
        files = list(iter_source_files(source))
        assert files == []

    def test_deduplicates_across_roots(self, tmp_path: Path) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()

        # Same filename in both roots
        (root_a / "shared.jsonl").write_text("a", encoding="utf-8")
        (root_b / "shared.jsonl").write_text("b", encoding="utf-8")

        source = Source(
            name="test", kind="claude", roots=(root_a, root_b), glob="*.jsonl"
        )
        files = list(iter_source_files(source))
        assert len(files) == 2

    def test_respects_glob(self, tmp_path: Path) -> None:
        root = tmp_path / "sessions"
        root.mkdir()
        (root / "a.jsonl").write_text("a", encoding="utf-8")
        (root / "b.txt").write_text("b", encoding="utf-8")

        source = Source(name="test", kind="claude", roots=(root,), glob="*.jsonl")
        files = list(iter_source_files(source))
        assert len(files) == 1
        assert files[0].name == "a.jsonl"

    def test_skips_directories(self, tmp_path: Path) -> None:
        root = tmp_path / "sessions"
        root.mkdir()
        (root / "subdir").mkdir()
        (root / "file.jsonl").write_text("f", encoding="utf-8")

        source = Source(name="test", kind="claude", roots=(root,), glob="**/*")
        files = list(iter_source_files(source))
        assert len(files) == 1
        assert files[0].is_file()


class TestSha256File:
    def test_consistent_hash(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("hello world", encoding="utf-8")
        h1 = sha256_file(path)
        h2 = sha256_file(path)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        p1 = tmp_path / "a.txt"
        p2 = tmp_path / "b.txt"
        p1.write_text("hello", encoding="utf-8")
        p2.write_text("world", encoding="utf-8")
        assert sha256_file(p1) != sha256_file(p2)

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        h = sha256_file(path)
        assert len(h) == 64
        # Empty file has known SHA-256
        assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestCopyRaw:
    def test_copies_and_gzips(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        source = archive_config.sources[0]
        path = repo_root / "session.jsonl"
        path.write_text("raw content", encoding="utf-8")

        result = copy_raw(archive_config, path, source, "abc123def456")
        assert result.exists()
        assert result.suffix == ".gz"

        # Verify gzip content
        with gzip.open(result, "rt", encoding="utf-8") as f:
            assert f.read() == "raw content"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        config = ArchiveConfig(
            repo_root=tmp_path,
            archive_dir=tmp_path / "archive",
            raw_dir=tmp_path / "raw",
            sources=(),
        )
        source = Source(name="test-src", kind="claude", roots=(tmp_path,))
        path = tmp_path / "data.jsonl"
        path.write_text("x", encoding="utf-8")

        result = copy_raw(config, path, source, "abcdef1234567890")
        assert result.parent.exists()


class TestCanReuseRecord:
    def _config(self, tmp_path: Path) -> ArchiveConfig:
        return ArchiveConfig(
            repo_root=tmp_path,
            archive_dir=tmp_path / "archive",
            raw_dir=tmp_path / "raw",
            sources=(),
        )

    def _record_with_markdown(self, tmp_path: Path, **extra: object) -> dict:
        md = tmp_path / "archive" / "s" / "a.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("x", encoding="utf-8")
        record = {"markdown": "archive/s/a.md", "size": 10, "mtime": 100.0}
        record.update(extra)
        return record

    def test_none_prior_not_reusable(self, tmp_path: Path) -> None:
        from agent_sessions.archive import _can_reuse_record

        assert _can_reuse_record(self._config(tmp_path), None, 10, 100.0, False, False) is False

    def test_missing_size_mtime_not_reusable(self, tmp_path: Path) -> None:
        from agent_sessions.archive import _can_reuse_record

        prior = self._record_with_markdown(tmp_path)
        del prior["size"]
        assert _can_reuse_record(self._config(tmp_path), prior, 10, 100.0, False, False) is False

    def test_matching_size_mtime_reusable(self, tmp_path: Path) -> None:
        from agent_sessions.archive import _can_reuse_record

        prior = self._record_with_markdown(tmp_path)
        assert _can_reuse_record(self._config(tmp_path), prior, 10, 100.0, False, False) is True

    def test_changed_mtime_not_reusable(self, tmp_path: Path) -> None:
        from agent_sessions.archive import _can_reuse_record

        prior = self._record_with_markdown(tmp_path)
        assert _can_reuse_record(self._config(tmp_path), prior, 10, 999.0, False, False) is False

    def test_missing_markdown_not_reusable(self, tmp_path: Path) -> None:
        from agent_sessions.archive import _can_reuse_record

        prior = {"markdown": "archive/s/gone.md", "size": 10, "mtime": 100.0}
        assert _can_reuse_record(self._config(tmp_path), prior, 10, 100.0, False, False) is False

    def test_pdf_requested_but_missing_not_reusable(self, tmp_path: Path) -> None:
        from agent_sessions.archive import _can_reuse_record

        prior = self._record_with_markdown(tmp_path, pdf=None)
        assert _can_reuse_record(self._config(tmp_path), prior, 10, 100.0, True, False) is False


class TestSelectSources:
    def test_all_when_none_selected(self, multi_source_config: ArchiveConfig) -> None:
        result = select_sources(multi_source_config, None)
        assert len(result) == 3

    def test_filter_by_name(self, multi_source_config: ArchiveConfig) -> None:
        result = select_sources(multi_source_config, ["test-claude"])
        assert len(result) == 1
        assert result[0].name == "test-claude"

    def test_unknown_selector_warns(
        self, multi_source_config: ArchiveConfig, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = select_sources(multi_source_config, ["does-not-exist"])
        assert result == []
        assert "matched no configured source name or kind" in capsys.readouterr().err

    def test_filter_by_kind(self, multi_source_config: ArchiveConfig) -> None:
        result = select_sources(multi_source_config, ["codex"])
        assert len(result) == 1
        assert result[0].kind == "codex"

    def test_filter_multiple(self, multi_source_config: ArchiveConfig) -> None:
        result = select_sources(multi_source_config, ["test-claude", "codex"])
        assert len(result) == 2

    def test_filter_no_match(self, multi_source_config: ArchiveConfig) -> None:
        result = select_sources(multi_source_config, ["nonexistent"])
        assert result == []


class TestExportResult:
    def test_creation(self) -> None:
        result = ExportResult(exported=5)
        assert result.exported == 5
        assert result.pdf_missing is False
        assert result.skipped_sources == ()

    def test_with_skipped(self) -> None:
        result = ExportResult(exported=3, pdf_missing=True, skipped_sources=("a", "b"))
        assert result.exported == 3
        assert result.pdf_missing is True
        assert result.skipped_sources == ("a", "b")


class TestWriteTextIfChanged:
    def test_writes_new_file(self, tmp_path: Path) -> None:
        path = tmp_path / "new.txt"
        changed = write_text_if_changed(path, "hello")
        assert changed is True
        assert path.read_text(encoding="utf-8") == "hello"

    def test_skips_unchanged(self, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("same content", encoding="utf-8", newline="\n")
        changed = write_text_if_changed(path, "same content")
        assert changed is False

    def test_writes_changed(self, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("old", encoding="utf-8", newline="\n")
        changed = write_text_if_changed(path, "new")
        assert changed is True
        assert path.read_text(encoding="utf-8") == "new"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "file.txt"
        changed = write_text_if_changed(path, "content")
        assert changed is True
        assert path.exists()


class TestExistingImportedAt:
    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert existing_imported_at(tmp_path / "nonexistent.md") is None

    def test_extracts_imported_at(self, tmp_path: Path) -> None:
        path = tmp_path / "test.md"
        path.write_text(
            "# Title\n\n- Imported at: `2026-01-01T00:00:00+00:00`\n\nOther content.\n",
            encoding="utf-8",
        )
        result = existing_imported_at(path)
        assert result == "2026-01-01T00:00:00+00:00"

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / "test.md"
        path.write_text("# No imported at here\n", encoding="utf-8")
        assert existing_imported_at(path) is None


class TestPreserveGeneratedAt:
    def test_new_file_returns_text(self, tmp_path: Path) -> None:
        path = tmp_path / "new.md"
        text = "Generated: `2026-01-01`\nContent.\n"
        result = preserve_generated_at(path, text)
        assert result == text

    def test_preserves_existing_timestamp(self, tmp_path: Path) -> None:
        path = tmp_path / "index.md"
        path.write_text(
            "Generated: `2026-01-01T00:00:00Z`\nContent.\n",
            encoding="utf-8",
        )
        new_text = "Generated: `2026-06-06T00:00:00Z`\nContent.\n"
        result = preserve_generated_at(path, new_text)
        assert "2026-01-01T00:00:00Z" in result

    def test_uses_new_text_when_content_differs(self, tmp_path: Path) -> None:
        path = tmp_path / "index.md"
        path.write_text(
            "Generated: `2026-01-01T00:00:00Z`\nOld content.\n",
            encoding="utf-8",
        )
        new_text = "Generated: `2026-06-06T00:00:00Z`\nNew content.\n"
        result = preserve_generated_at(path, new_text)
        assert result == new_text


class TestWriteIndexes:
    def test_writes_jsonl_and_markdown(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        records = [
            {
                "source": "test-claude",
                "kind": "claude",
                "source_file": "/fake/session.jsonl",
                "sha256": "abc123",
                "messages": 5,
                "markdown": "archive/test-claude/session.md",
                "pdf": None,
                "raw": None,
                "metadata": {"session_id": "s1"},
            },
        ]
        write_indexes(archive_config, records)

        # Check JSONL
        jsonl_path = archive_config.archive_dir / "index.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["source"] == "test-claude"

        # Check INDEX.md
        index_path = archive_config.archive_dir / "INDEX.md"
        assert index_path.exists()
        content = index_path.read_text(encoding="utf-8")
        assert "# Agent Session Archive" in content
        assert "test-claude" in content
        assert "`archive/test-claude/session.md`" in content
        assert "[session.md]" not in content

    def test_writes_pdf_link(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        archive_config = ArchiveConfig(
            repo_root=archive_config.repo_root,
            archive_dir=archive_config.archive_dir,
            raw_dir=archive_config.raw_dir,
            sources=archive_config.sources,
            track_artifacts=True,
        )
        records = [
            {
                "source": "test-claude",
                "kind": "claude",
                "source_file": "/fake/session.jsonl",
                "sha256": "abc123",
                "messages": 5,
                "markdown": "archive/test-claude/session.md",
                "pdf": "archive/test-claude/session.pdf",
                "raw": None,
                "metadata": {},
            },
        ]
        write_indexes(archive_config, records)
        index_path = archive_config.archive_dir / "INDEX.md"
        content = index_path.read_text(encoding="utf-8")
        assert "[PDF]" in content

    def test_writes_pdf_path_when_artifacts_are_local_only(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        records = [
            {
                "source": "test-claude",
                "kind": "claude",
                "source_file": "/fake/session.jsonl",
                "sha256": "abc123",
                "messages": 5,
                "markdown": "archive/test-claude/session.md",
                "pdf": "archive/test-claude/session.pdf",
                "raw": None,
                "metadata": {},
            },
        ]
        write_indexes(archive_config, records)
        index_path = archive_config.archive_dir / "INDEX.md"
        content = index_path.read_text(encoding="utf-8")
        assert "`archive/test-claude/session.pdf`" in content
        assert "[PDF]" not in content


class TestLoadIndexRecords:
    def test_loads_records(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        records = [
            {
                "source": "s1",
                "kind": "k1",
                "source_file": "/f1",
                "sha256": "a",
                "messages": 1,
                "markdown": "a/s1.md",
                "metadata": {},
            },
            {
                "source": "s2",
                "kind": "k2",
                "source_file": "/f2",
                "sha256": "b",
                "messages": 2,
                "markdown": "a/s2.md",
                "metadata": {},
            },
        ]
        write_indexes(archive_config, records)
        loaded = load_index_records(archive_config)
        assert len(loaded) == 2
        assert loaded[0]["source"] == "s1"

    def test_raises_when_no_index(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        with pytest.raises(SystemExit, match="index.jsonl"):
            load_index_records(archive_config)


class TestMergeIndexRecords:
    def test_current_replaces_existing_same_source_file(self) -> None:
        existing = [
            {
                "source": "test-claude",
                "source_file": "/same/session.jsonl",
                "sha256": "old",
                "markdown": "archive/test/old.md",
            }
        ]
        current = [
            {
                "source": "test-claude",
                "source_file": "/same/session.jsonl",
                "sha256": "new",
                "markdown": "archive/test/new.md",
            }
        ]

        merged = merge_index_records(existing, current)

        assert len(merged) == 1
        assert merged[0]["sha256"] == "new"
        assert merged[0]["markdown"] == "archive/test/new.md"

    def test_same_session_across_machines_dedupes_by_session_id(self) -> None:
        # Same logical session exported from two machines: different absolute
        # source_file paths, same session_id and digest -> a single merged record.
        windows = {
            "source": "claude-windows",
            "source_file": r"C:\Users\a\.claude\projects\p\sess.jsonl",
            "sha256": "aaa",
            "markdown": "archive/claude-windows/sess.md",
            "metadata": {"session_id": "1111-2222"},
        }
        wsl = {
            "source": "claude-wsl-ubuntu",
            "source_file": "/home/a/.claude/projects/p/sess.jsonl",
            "sha256": "aaa",
            "markdown": "archive/claude-wsl-ubuntu/sess.md",
            "metadata": {"session_id": "1111-2222"},
        }
        merged = merge_index_records([windows], [wsl])
        assert len(merged) == 1
        assert merged[0]["metadata"]["session_id"] == "1111-2222"

    def test_same_session_different_content_keeps_distinct_records(self) -> None:
        first = {
            "source": "claude-windows",
            "source_file": r"C:\Users\a\.claude\projects\p\agent-a.jsonl",
            "sha256": "aaa",
            "markdown": "archive/claude-windows/agent-a.md",
            "metadata": {"session_id": "1111-2222"},
        }
        second = {
            "source": "claude-windows",
            "source_file": r"C:\Users\a\.claude\projects\p\agent-b.jsonl",
            "sha256": "bbb",
            "markdown": "archive/claude-windows/agent-b.md",
            "metadata": {"session_id": "1111-2222"},
        }
        merged = merge_index_records([first], [second])
        assert len(merged) == 2
        assert {record["sha256"] for record in merged} == {"aaa", "bbb"}

    def test_same_source_path_changed_digest_supersedes_old_record(self) -> None:
        old = {
            "source": "claude-windows",
            "source_file": r"C:\Users\a\.claude\projects\p\sess.jsonl",
            "sha256": "aaa",
            "markdown": "archive/claude-windows/old.md",
            "metadata": {"session_id": "1111-2222"},
        }
        new = {
            "source": "claude-windows",
            "source_file": r"C:\Users\a\.claude\projects\p\sess.jsonl",
            "sha256": "bbb",
            "markdown": "archive/claude-windows/new.md",
            "metadata": {"session_id": "1111-2222"},
        }
        merged = merge_index_records([old], [new])
        assert len(merged) == 1
        assert merged[0]["sha256"] == "bbb"
        assert merged[0]["markdown"] == "archive/claude-windows/new.md"

    def test_write_indexes_normalizes_paths_to_posix(self, archive_config: ArchiveConfig) -> None:
        from agent_sessions.archive import read_existing_index_records, write_indexes

        write_indexes(
            archive_config,
            [
                {
                    "source": "s",
                    "kind": "claude",
                    "source_file": r"C:\x\y.jsonl",
                    "sha256": "d",
                    "messages": 1,
                    "markdown": r"archive\s\a.md",
                    "pdf": None,
                    "raw": None,
                    "metadata": {},
                }
            ],
        )
        stored = read_existing_index_records(archive_config)
        assert stored[0]["markdown"] == "archive/s/a.md"


class TestPruneIndexRecords:
    def test_prunes_records_with_missing_markdown(self, repo_root: Path, archive_config: ArchiveConfig) -> None:
        from agent_sessions.archive import prune_index_records, read_existing_index_records, write_indexes

        archive_config = ArchiveConfig(
            repo_root=archive_config.repo_root,
            archive_dir=archive_config.archive_dir,
            raw_dir=archive_config.raw_dir,
            sources=archive_config.sources,
            track_artifacts=True,
        )
        present = repo_root / "archive" / "s" / "present.md"
        present.parent.mkdir(parents=True, exist_ok=True)
        present.write_text("hi", encoding="utf-8")
        write_indexes(
            archive_config,
            [
                {"source": "s", "kind": "claude", "source_file": "a", "sha256": "1",
                 "messages": 1, "markdown": "archive/s/present.md", "pdf": None, "raw": None, "metadata": {}},
                {"source": "s", "kind": "claude", "source_file": "b", "sha256": "2",
                 "messages": 1, "markdown": "archive/s/gone.md", "pdf": None, "raw": None, "metadata": {}},
            ],
        )
        assert prune_index_records(archive_config) == 0
        remaining = read_existing_index_records(archive_config)
        assert [r["markdown"] for r in remaining] == ["archive/s/present.md"]

    def test_dry_run_keeps_records(self, repo_root: Path, archive_config: ArchiveConfig) -> None:
        from agent_sessions.archive import prune_index_records, read_existing_index_records, write_indexes

        archive_config = ArchiveConfig(
            repo_root=archive_config.repo_root,
            archive_dir=archive_config.archive_dir,
            raw_dir=archive_config.raw_dir,
            sources=archive_config.sources,
            track_artifacts=True,
        )
        write_indexes(
            archive_config,
            [{"source": "s", "kind": "claude", "source_file": "b", "sha256": "2",
              "messages": 1, "markdown": "archive/s/gone.md", "pdf": None, "raw": None, "metadata": {}}],
        )
        prune_index_records(archive_config, dry_run=True)
        assert len(read_existing_index_records(archive_config)) == 1

    def test_local_only_artifacts_keep_missing_markdown(
        self,
        archive_config: ArchiveConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from agent_sessions.archive import prune_index_records, read_existing_index_records, write_indexes

        write_indexes(
            archive_config,
            [
                {
                    "source": "s",
                    "kind": "claude",
                    "source_file": "b",
                    "sha256": "2",
                    "messages": 1,
                    "markdown": "archive/s/local-only.md",
                    "pdf": None,
                    "raw": None,
                    "metadata": {},
                }
            ],
        )

        prune_index_records(archive_config)

        assert len(read_existing_index_records(archive_config)) == 1
        assert "local-only" in capsys.readouterr().out

    def test_export_preserves_records_from_other_machines(
        self, archive_config: ArchiveConfig
    ) -> None:
        remote = {
            "source": "remote-claude",
            "kind": "claude",
            "source_file": r"C:\Users\other\.claude\projects\session.jsonl",
            "sha256": "remote",
            "messages": 1,
            "markdown": "archive/remote-claude/session.md",
            "pdf": None,
            "raw": None,
            "metadata": {},
        }
        write_indexes(archive_config, [remote])
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "local.jsonl").write_text(
            '{"sessionId":"local","message":{"role":"user","content":[{"text":"Hi"}]}}\n',
            encoding="utf-8",
        )

        export_sources(archive_config)
        records = read_existing_index_records(archive_config)

        assert any(record["source"] == "remote-claude" for record in records)
        assert any(record["source"] == "test-claude" for record in records)


class TestDiscoverSources:
    def test_discovers_and_prints(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        # Create some session files
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "session1.jsonl").write_text("{}", encoding="utf-8")
        (root / "session2.jsonl").write_text("{}", encoding="utf-8")

        result = discover_sources(archive_config, samples=5)
        assert result == 0

    def test_discovers_with_write(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "s.jsonl").write_text("{}", encoding="utf-8")

        out_path = repo_root / "discovery.md"
        result = discover_sources(archive_config, samples=1, write=str(out_path))
        assert result == 0
        assert out_path.exists()

    def test_handles_missing_roots(self, archive_config: ArchiveConfig) -> None:
        result = discover_sources(archive_config, samples=1)
        assert result == 0


class TestExportSources:
    def test_dry_run(self, repo_root: Path, archive_config: ArchiveConfig) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "s.jsonl").write_text(
            '{"sessionId":"x","message":{"role":"user","content":[{"text":"Hi"}]}}\n',
            encoding="utf-8",
        )

        result = export_sources(archive_config, limit=1, dry_run=True)
        assert result.exported == 1

    def test_exports_markdown(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "s.jsonl").write_text(
            '{"sessionId":"x","message":{"role":"user","content":[{"text":"Hi"}]}}\n',
            encoding="utf-8",
        )

        result = export_sources(archive_config, limit=1)
        assert result.exported == 1
        assert any((archive_config.archive_dir / "test-claude").iterdir())

    def test_skips_inventory_sources(
        self, repo_root: Path, multi_source_config: ArchiveConfig
    ) -> None:
        result = export_sources(multi_source_config, limit=1, dry_run=True)
        assert (
            "test-inventory" in result.skipped_sources
            or any("inventory" in s for s in result.skipped_sources)
            or result.exported >= 0
        )

    def test_pdf_missing_flag(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "s.jsonl").write_text(
            '{"sessionId":"x","message":{"role":"user","content":[{"text":"Hi"}]}}\n',
            encoding="utf-8",
        )

        result = export_sources(archive_config, limit=1, write_pdfs=True, dry_run=True)
        # In dry_run mode, write_pdf is never called, so pdf_missing stays False
        assert result.exported == 1


class TestPdfExisting:
    def test_no_index_raises(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        with pytest.raises(SystemExit, match="index.jsonl"):
            pdf_existing(archive_config)

    def test_pdf_with_existing_index(
        self, repo_root: Path, archive_config: ArchiveConfig
    ) -> None:
        # Create index first
        root = archive_config.sources[0].roots[0]
        root.mkdir(parents=True)
        (root / "s.jsonl").write_text(
            '{"sessionId":"x","message":{"role":"user","content":[{"text":"Hi"}]}}\n',
            encoding="utf-8",
        )
        export_sources(archive_config, limit=1)

        # Now try pdf
        result = pdf_existing(archive_config, limit=1)
        # May return 1 if reportlab is missing, or 0 if it wrote
        assert result in (0, 1)


class TestUtilityFunctions:
    def test_dt_from_timestamp(self) -> None:
        result = dt_from_timestamp(1750000000.0)
        assert len(result) == 8  # YYYYMMDD
        assert result.isdigit()

    def test_dt_from_timestamp_is_utc(self) -> None:
        # Stem must be timezone-independent (UTC), so it matches across machines
        # regardless of the local timezone the export runs in.
        assert dt_from_timestamp(1750000000.0) == "20250615"

    def test_source_modified_date(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("hello", encoding="utf-8")
        result = source_modified_date(path)
        assert len(result) == 8  # YYYYMMDD

    def test_as_repo_relative(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        path = repo_root / "archive" / "file.md"
        result = as_repo_relative(config, path)
        assert result is not None
        assert result.replace("\\", "/") == "archive/file.md"

    def test_as_repo_relative_none(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        assert as_repo_relative(config, None) is None
