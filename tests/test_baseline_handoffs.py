"""Tests for report-only baseline handoff auditing."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from agent_sessions.baseline_handoffs import (
    ArchiveHandoffHit,
    archive_handoff_hit,
    baseline_handoffs_audit,
    baseline_handoffs_index,
    baseline_handoffs_proposals,
    build_handoff_audit,
    build_handoff_index_records,
    build_handoff_proposals,
    handoff_index_record,
    handoff_sections,
    has_start_here_pointer,
    is_probable_handoff,
    load_handoff_index,
    project_page_updates,
    project_slug_for_raw,
    project_slug_map,
    render_handoff_audit,
    render_handoff_index_jsonl,
    render_project_handoff_feed,
    scan_archive_handoff_hits,
)
from agent_sessions.baseline_ingest import archive_references, validate_proposal
from agent_sessions.baseline_settings import load_baseline_settings
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


def _write_archive_handoff(repo_root: Path, *, project_raw: str = "C:/Work/Project", session_id: str = "s1") -> None:
    archive_dir = repo_root / "archive"
    markdown_dir = archive_dir / "codex"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_dir / f"{session_id}.md"
    markdown_path.write_text(_handoff_text(), encoding="utf-8")
    (archive_dir / "index.jsonl").write_text(
        json.dumps(
            {
                "source": "codex",
                "kind": "codex",
                "source_file": f"/fake/{session_id}.jsonl",
                "sha256": "abc",
                "messages": 3,
                "markdown": f"archive/codex/{session_id}.md",
                "metadata": {"session_id": session_id, "project": project_raw},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _hit(
    *,
    source: str = "codex",
    source_file: str = "/fake/session.jsonl",
    markdown_path: str = "archive/codex/session.md",
    session_id: str = "session",
    project_raw: str = "C:/Work/Project",
    sections: tuple[str, ...] = (),
    signals: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> ArchiveHandoffHit:
    return ArchiveHandoffHit(
        source=source,
        source_file=source_file,
        markdown_path=markdown_path,
        session_id=session_id,
        project_raw=project_raw,
        sections=sections,
        signals=signals,
        warnings=warnings,
    )


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

    def test_probable_handoff_falls_back_to_heading_count(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.md"
        text = "## You Are Here\n\nNow.\n\n## Ramp-Up Kit\n\nDocs.\n"
        assert is_probable_handoff(text, path) is True


class TestBuildHandoffAudit:
    def test_analyzes_repo_handoff_and_memory_pointer(self, repo_root: Path) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        (repo_root / "MEMORY.md").write_text(
            '- ▶ Start here: `memory/session-handoff.md`\n',
            encoding="utf-8",
        )
        audit = build_handoff_audit(
            _config(repo_root),
            now=dt.datetime(2026, 7, 7, tzinfo=dt.UTC),
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
            now=dt.datetime(2026, 7, 7, tzinfo=dt.UTC),
        )
        report = render_handoff_audit(audit)
        assert "MEMORY.md start-here pointer" in report
        assert "Handoff-derived proposal generation is implemented" in report

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
            now=dt.datetime(2026, 7, 7, tzinfo=dt.UTC),
        )
        assert audit.archive_records_scanned == 1
        assert len(audit.archive_hits) == 1
        assert audit.archive_hits[0].session_id == "s1"

    def test_archive_scan_skips_unusable_records(self, repo_root: Path) -> None:
        archive_dir = repo_root / "archive"
        markdown_dir = archive_dir / "codex"
        markdown_dir.mkdir(parents=True, exist_ok=True)
        (markdown_dir / "plain.md").write_text("# Notes\n\nNothing handoff-like.\n", encoding="utf-8")
        records = [
            {"source": "codex"},
            {"source": "codex", "markdown": "archive/codex/missing.md"},
            {"source": "codex", "markdown": "archive/codex/plain.md"},
        ]
        assert scan_archive_handoff_hits(_config(repo_root), records) == []

    def test_archive_hit_ignores_non_dict_metadata(self) -> None:
        record = {"source": "codex", "markdown": "archive/codex/session.md", "metadata": "not-a-dict"}
        hit = archive_handoff_hit(record, _handoff_text(), "archive/codex/session.md")
        assert hit.session_id is None
        assert hit.project_raw is None


class TestHandoffIndex:
    def test_builds_index_record_with_trace(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root, project_raw="C:/Users/alice/Projects/Agent Sessions")
        config = _config(repo_root)
        settings = load_baseline_settings(config)
        records = build_handoff_index_records(config, settings)
        assert len(records) == 1
        record = records[0]
        assert record.source_kind == "repo-handoff"
        assert record.source_file == "/fake/s1.jsonl"
        assert record.markdown_path == "archive/codex/s1.md"
        assert record.project_slug == "agent-sessions"
        assert record.trace[0]["transform"] == "baseline handoffs index"

    def test_project_slug_handles_url_encoded_windows_path(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        assert project_slug_for_raw(settings, "%2FC%3A%2FUsers%2Falice%2FProjects%2FKhelSutra") == "khelsutra"

    def test_project_slug_handles_hyphen_encoded_windows_path(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        assert project_slug_for_raw(settings, "C--Users-alice-Projects-sports-data-collector") == "sports-data-collector"

    def test_project_slug_empty_raw_becomes_unknown(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        assert project_slug_for_raw(settings, "") == "unknown-project"

    def test_project_slug_prefers_stronger_alias_match(self, repo_root: Path) -> None:
        (repo_root / "config" / "baseline.toml").write_text(
            '[[pilots]]\nslug = "tester"\nkind = "github-account"\naliases = ["tester"]\n\n'
            '[[pilots]]\nslug = "khelsutra"\nkind = "github-organization"\naliases = ["khelsutra"]\n',
            encoding="utf-8",
        )
        settings = load_baseline_settings(_config(repo_root))
        raw = "%2Fhome%2Ftester%2Fprojects%2FVerifiers%2Fkhelsutra%2Ftmp"
        assert project_slug_for_raw(settings, raw) == "khelsutra"

    def test_project_slug_collisions_get_stable_disambiguators(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        first = _hit(source_file="/one.jsonl", markdown_path="archive/codex/one.md", session_id="one", project_raw="C:/Work/App")
        second = _hit(source_file="/two.jsonl", markdown_path="archive/codex/two.md", session_id="two", project_raw="D:/Other/App")
        third = _hit(
            source_file="/three.jsonl",
            markdown_path="archive/codex/three.md",
            session_id="three",
            project_raw="C:/Work/Other",
        )
        slugs = project_slug_map(settings, (first, second, third))
        assert slugs[first].startswith("app-")
        assert slugs[second].startswith("app-")
        assert slugs[first] != slugs[second]
        assert slugs[third] == "other"

    def test_project_slug_does_not_disambiguate_configured_pilots(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        first = _hit(source_file="/one.jsonl", markdown_path="archive/codex/one.md", session_id="one", project_raw="C:/Work/test-pilot")
        second = _hit(
            source="claude",
            source_file="/two.jsonl",
            markdown_path="archive/claude/two.md",
            session_id="two",
            project_raw="C--Users-alice-Projects-test-pilot",
        )
        slugs = project_slug_map(settings, (first, second))
        assert slugs[first] == "test-pilot"
        assert slugs[second] == "test-pilot"

    def test_renders_handoff_index_jsonl(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root)
        config = _config(repo_root)
        records = build_handoff_index_records(config, load_baseline_settings(config))
        rendered = render_handoff_index_jsonl(records)
        payload = json.loads(rendered)
        assert payload["id"].startswith("handoff.")
        assert payload["project_slug"] == "project"

    def test_loads_handoff_index_with_clean_trace(self, repo_root: Path) -> None:
        path = repo_root / "baseline" / "handoffs" / "index.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "id": "handoff.test",
                    "source_kind": "repo-handoff",
                    "source": "codex",
                    "source_file": "/fake/session.jsonl",
                    "markdown_path": "archive/codex/session.md",
                    "session_id": "session",
                    "project_raw": "Project",
                    "project_slug": "project",
                    "sections": ["You Are Here"],
                    "signals": ["session handoff"],
                    "warnings": [],
                    "trace": [{"markdown_path": "archive/codex/session.md", "empty": ""}, "ignored"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        records = load_handoff_index(path)
        assert records[0].trace == ({"markdown_path": "archive/codex/session.md"},)

    def test_project_feed_summarizes_more_than_ten_records(self) -> None:
        records = [
            _hit(markdown_path=f"archive/codex/{index}.md", session_id=str(index))
            for index in range(11)
        ]
        rendered = render_project_handoff_feed("project", [
            handoff_index_record(hit, "project") for hit in records
        ], generated_at="2026-07-07")
        assert "`1` more indexed handoff candidate(s)." in rendered

    def test_project_page_feed_reuses_date_when_content_unchanged(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        record = handoff_index_record(_hit(), "project")
        page = repo_root / "baseline" / "projects" / "project" / "README.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        existing_block = render_project_handoff_feed("project", [record], generated_at="2026-07-07")
        page.write_text(f"# project\n\n{existing_block}\n", encoding="utf-8")

        updates = project_page_updates(settings, [record], generated_at="2026-07-08")

        assert "**Generated at:** 2026-07-07" in updates[page]
        assert "**Generated at:** 2026-07-08" not in updates[page]

    def test_project_page_feed_updates_date_when_content_changes(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        first = handoff_index_record(_hit(), "project")
        second = handoff_index_record(
            _hit(markdown_path="archive/codex/s2.md", session_id="s2"),
            "project",
        )
        page = repo_root / "baseline" / "projects" / "project" / "README.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        existing_block = render_project_handoff_feed("project", [first], generated_at="2026-07-07")
        page.write_text(f"# project\n\n{existing_block}\n", encoding="utf-8")

        updates = project_page_updates(settings, [first, second], generated_at="2026-07-08")

        assert "**Generated at:** 2026-07-08" in updates[page]
        assert "[archive/codex/s2.md](../../../archive/codex/s2.md)" in updates[page]

    def test_project_page_feed_uses_new_date_when_existing_block_has_no_date(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        record = handoff_index_record(_hit(), "project")
        page = repo_root / "baseline" / "projects" / "project" / "README.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "# project\n\n"
            '<!-- baseline:begin id="handoffs.index" -->\n'
            "## Handoff Signals\n\n"
            "Old generated content.\n"
            '<!-- baseline:end id="handoffs.index" -->\n',
            encoding="utf-8",
        )

        updates = project_page_updates(settings, [record], generated_at="2026-07-08")

        assert "**Generated at:** 2026-07-08" in updates[page]


class TestBaselineHandoffsAudit:
    def test_writes_only_audit_file(self, repo_root: Path) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        result = baseline_handoffs_audit(_config(repo_root))
        assert result == 0
        assert (repo_root / "baseline" / "handoffs" / "audit.md").exists()
        assert not (repo_root / "baseline" / "handoffs" / "index.jsonl").exists()
        assert not list((repo_root / "baseline" / "proposals").glob("*.json"))

    def test_dry_run_does_not_write(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (repo_root / "SESSION_HANDOFF.md").write_text(_handoff_text(), encoding="utf-8")
        result = baseline_handoffs_audit(_config(repo_root), dry_run=True)
        assert result == 0
        assert "Would write" in capsys.readouterr().out
        assert not (repo_root / "baseline" / "handoffs" / "audit.md").exists()


class TestBaselineHandoffsIndex:
    def test_writes_index_and_project_page_feed(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root)
        page = repo_root / "baseline" / "projects" / "project" / "README.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("# project\n\nHuman note.\n", encoding="utf-8")
        result = baseline_handoffs_index(_config(repo_root))
        assert result == 0
        index = repo_root / "baseline" / "handoffs" / "index.jsonl"
        assert index.exists()
        payload = json.loads(index.read_text(encoding="utf-8"))
        assert payload["markdown_path"] == "archive/codex/s1.md"
        page_text = page.read_text(encoding="utf-8")
        assert "Human note." in page_text
        assert '<!-- baseline:begin id="handoffs.index" -->' in page_text
        assert "Indexed handoff candidates: `1`." in page_text
        assert "[archive/codex/s1.md](../../../archive/codex/s1.md)" in page_text
        assert not list((repo_root / "baseline" / "proposals").glob("*.json"))

    def test_index_does_not_create_unknown_project_pages(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root)
        result = baseline_handoffs_index(_config(repo_root))
        assert result == 0
        assert (repo_root / "baseline" / "handoffs" / "index.jsonl").exists()
        assert not (repo_root / "baseline" / "projects" / "project" / "README.md").exists()

    def test_dry_run_does_not_write_index_or_project_page(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _write_archive_handoff(repo_root)
        result = baseline_handoffs_index(_config(repo_root), dry_run=True)
        assert result == 0
        assert "Would write" in capsys.readouterr().out
        assert not (repo_root / "baseline" / "handoffs" / "index.jsonl").exists()
        assert not (repo_root / "baseline" / "projects" / "project" / "README.md").exists()


class TestHandoffProposals:
    def test_builds_valid_project_proposal_with_trace(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        hit = _hit(
            markdown_path="archive/codex/session.md",
            session_id="session",
            project_raw="test-pilot",
            sections=("You Are Here", "Ramp-Up Kit"),
            signals=("session handoff", "ramp-up kit"),
        )
        proposal = build_handoff_proposals(settings, [handoff_index_record(hit, "test-pilot")])[0]
        assert proposal["id"] == "handoff.test-pilot.handoff-signals"
        assert proposal["scope"] == "project:test-pilot"
        assert proposal["generated_by"] == "baseline handoffs proposals"
        assert proposal["trace"][0]["transform"] == "baseline handoffs proposals"
        refs = archive_references([{"markdown": "archive/codex/session.md", "metadata": {"session_id": "session"}}])
        assert validate_proposal(proposal, refs) == []

    def test_builds_warning_question_for_nonconforming_handoffs(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        hit = _hit(project_raw="test-pilot", warnings=("no standard handoff headings",))
        proposal = build_handoff_proposals(settings, [handoff_index_record(hit, "test-pilot")])[0]
        assert "1 indexed handoff candidate(s) lack standard headings" in proposal["open_questions"][1]

    def test_build_skips_unknown_project_slugs(self, repo_root: Path) -> None:
        settings = load_baseline_settings(_config(repo_root))
        hit = _hit(project_raw="", markdown_path="archive/codex/session.md")
        assert build_handoff_proposals(settings, [handoff_index_record(hit, "unknown-project")]) == []

    def test_missing_index_raises(self, repo_root: Path) -> None:
        with pytest.raises(SystemExit, match="Run `baseline handoffs index` first"):
            baseline_handoffs_proposals(_config(repo_root), index=Path("missing-index.jsonl"))

    def test_writes_handoff_proposals_from_index(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root, project_raw="test-pilot")
        assert baseline_handoffs_index(_config(repo_root)) == 0
        result = baseline_handoffs_proposals(_config(repo_root))
        assert result == 0
        proposal_path = repo_root / "baseline" / "proposals" / "handoff.test-pilot.handoff-signals.json"
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        assert proposal["source_kind"] == "repo-handoff"
        assert proposal["trace"][0]["markdown_path"] == "archive/codex/s1.md"

    def test_accepts_relative_index_and_output_dir(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root, project_raw="test-pilot")
        assert baseline_handoffs_index(_config(repo_root), output=Path("custom-index.jsonl")) == 0

        result = baseline_handoffs_proposals(
            _config(repo_root),
            index=Path("custom-index.jsonl"),
            output_dir=Path("custom-proposals"),
        )

        assert result == 0
        assert (repo_root / "custom-proposals" / "handoff.test-pilot.handoff-signals.json").exists()

    def test_proposals_dry_run_does_not_write(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _write_archive_handoff(repo_root, project_raw="test-pilot")
        assert baseline_handoffs_index(_config(repo_root)) == 0
        result = baseline_handoffs_proposals(_config(repo_root), dry_run=True)
        assert result == 0
        assert "Would write 1 handoff proposal(s)." in capsys.readouterr().out
        assert not (repo_root / "baseline" / "proposals" / "handoff.test-pilot.handoff-signals.json").exists()

    def test_proposals_require_positive_record_limit(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root, project_raw="test-pilot")
        assert baseline_handoffs_index(_config(repo_root)) == 0
        with pytest.raises(SystemExit, match="max-records-per-project"):
            baseline_handoffs_proposals(_config(repo_root), max_records_per_project=0)

    def test_refuses_to_overwrite_human_proposal(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root, project_raw="test-pilot")
        assert baseline_handoffs_index(_config(repo_root)) == 0
        proposal_path = repo_root / "baseline" / "proposals" / "handoff.test-pilot.handoff-signals.json"
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text('{"id": "handoff.test-pilot.handoff-signals"}\n', encoding="utf-8")
        with pytest.raises(SystemExit, match="Refusing to overwrite non-generated proposal"):
            baseline_handoffs_proposals(_config(repo_root))

    def test_refuses_to_overwrite_invalid_json_proposal(self, repo_root: Path) -> None:
        _write_archive_handoff(repo_root, project_raw="test-pilot")
        assert baseline_handoffs_index(_config(repo_root)) == 0
        proposal_path = repo_root / "baseline" / "proposals" / "handoff.test-pilot.handoff-signals.json"
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text("{invalid json\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="Refusing to overwrite non-JSON proposal"):
            baseline_handoffs_proposals(_config(repo_root))
