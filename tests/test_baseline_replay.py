"""Tests for deterministic replay selection (K8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.baseline_replay import (
    baseline_replay_select,
    evaluate_record,
    infer_kind,
    load_manifest,
    render_manifest_jsonl,
    select_replay_candidates,
    selected_manifest_entries,
)
from agent_sessions.config import ArchiveConfig


def _config(repo_root: Path) -> ArchiveConfig:
    return ArchiveConfig(repo_root=repo_root, archive_dir=repo_root / "archive", raw_dir=repo_root / "raw", sources=())


PLANNING_PROMPT = (
    "Please produce a detailed design plan for the badminton highlight indexer. "
    "It should cover the ingestion pipeline, the scoring model, the storage schema, "
    "and a phased rollout with explicit milestones and open questions to resolve."
)


def _planning_markdown() -> str:
    return (
        "# Session\n\n"
        "### 1. user\n\n"
        f"{PLANNING_PROMPT}\n\n"
        "### 2. assistant\n\n"
        "Here is the design plan.\n\n"
        "## Rollout\n\n"
        "| Phase | Deliverable |\n"
        "|---|---|\n"
        "| P1 | Ingestion |\n"
        "| P2 | Scoring |\n"
    )


def _coding_markdown() -> str:
    return (
        "# Session\n\n"
        "### 1. user\n\n"
        "Fix the failing test in the parser module and update the fixtures accordingly please now.\n\n"
        "### 2. assistant\n\n"
        "```diff\n"
        "diff --git a/parser.py b/parser.py\n"
        "@@ -1,3 +1,4 @@\n"
        "-old\n"
        "+new\n"
        "```\n"
    )


def _write_archive(repo_root: Path, records: list[dict]) -> None:
    archive_dir = repo_root / "archive"
    lines = []
    for record in records:
        md_rel = record["markdown"].replace("\\", "/")
        md_path = repo_root / md_rel
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(record.pop("_body"), encoding="utf-8")
        lines.append(json.dumps(record))
    (archive_dir / "index.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _record(markdown: str, *, sha: str, session: str, messages: int, body: str, project: str = "demo") -> dict:
    return {
        "source": "codex-windows",
        "kind": "codex",
        "sha256": sha,
        "messages": messages,
        "markdown": markdown,
        "metadata": {"session_id": session, "project": project},
        "_body": body,
    }


class TestEvaluateRecord:
    def test_planning_session_is_eligible(self, repo_root: Path) -> None:
        _write_archive(
            repo_root,
            [_record("archive/demo/plan.md", sha="a" * 64, session="s1", messages=10, body=_planning_markdown())],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.eligible is True
        assert candidate.kind == "planning"
        assert candidate.exclusion_reasons == ()

    def test_coding_session_excluded(self, repo_root: Path) -> None:
        _write_archive(
            repo_root,
            [_record("archive/demo/code.md", sha="b" * 64, session="s2", messages=10, body=_coding_markdown())],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.eligible is False
        assert candidate.kind == "coding"
        assert any("coding session excluded" in reason for reason in candidate.exclusion_reasons)

    def test_missing_markdown_is_ineligible_not_dropped(self, repo_root: Path) -> None:
        (repo_root / "archive" / "index.jsonl").write_text(
            json.dumps(
                {
                    "source": "codex",
                    "sha256": "c" * 64,
                    "messages": 10,
                    "markdown": "archive/demo/missing.md",
                    "metadata": {"session_id": "s3"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.eligible is False
        assert candidate.exclusion_reasons == ("archive markdown file not found",)

    def test_record_without_markdown_returns_none(self, repo_root: Path) -> None:
        candidate = evaluate_record(_config(repo_root), {"sha256": "d" * 64, "messages": 5})
        assert candidate is None

    def test_too_few_messages_excluded(self, repo_root: Path) -> None:
        _write_archive(
            repo_root,
            [_record("archive/demo/tiny.md", sha="e" * 64, session="s4", messages=1, body=_planning_markdown())],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.eligible is False
        assert any("too few messages" in reason for reason in candidate.exclusion_reasons)


class TestExclusionReasons:
    @pytest.mark.parametrize(
        "messages, extra_turns, fragment",
        [
            (99, 0, "too many messages"),
            (10, 6, "not self-contained"),
        ],
    )
    def test_soft_exclusions(self, repo_root: Path, messages: int, extra_turns: int, fragment: str) -> None:
        body = _planning_markdown() + "".join(f"\n### user\n\nfollow up {i}\n" for i in range(extra_turns))
        _write_archive(
            repo_root,
            [_record("archive/demo/x.md", sha="1" * 64, session="s1", messages=messages, body=body)],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.eligible is False
        assert any(fragment in reason for reason in candidate.exclusion_reasons)

    def test_transcript_too_large(self, repo_root: Path) -> None:
        body = _planning_markdown() + "\n" + ("padding text " * 6000)
        _write_archive(
            repo_root,
            [_record("archive/demo/big.md", sha="1" * 64, session="s1", messages=10, body=body)],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert any("transcript too large" in reason for reason in candidate.exclusion_reasons)

    def test_short_prompt_and_no_deliverable(self, repo_root: Path) -> None:
        body = "# Session\n\n### 1. user\n\nhi\n\n### 2. assistant\n\nok\n"
        _write_archive(
            repo_root,
            [_record("archive/demo/thin.md", sha="1" * 64, session="s1", messages=10, body=body)],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert any("first prompt too short" in reason for reason in candidate.exclusion_reasons)
        assert any("no detectable deliverable" in reason for reason in candidate.exclusion_reasons)

    def test_deliverable_detected_via_section_heading(self, repo_root: Path) -> None:
        body = (
            "# Session\n\n### 1. user\n\n"
            f"{PLANNING_PROMPT}\n\n### 2. assistant\n\n"
            "Findings below.\n\n## Summary of Findings\n\nThe pipeline should stream events.\n"
        )
        _write_archive(
            repo_root,
            [_record("archive/demo/sec.md", sha="1" * 64, session="s1", messages=10, body=body)],
        )
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.eligible is True
        assert not any("no detectable deliverable" in reason for reason in candidate.exclusion_reasons)

    def test_empty_project_metadata_slug(self, repo_root: Path) -> None:
        record = _record("archive/demo/plan.md", sha="1" * 64, session="s1", messages=10, body=_planning_markdown())
        record["metadata"] = {"session_id": "s1"}
        _write_archive(repo_root, [record])
        records = load_manifest(repo_root / "archive" / "index.jsonl")
        candidate = evaluate_record(_config(repo_root), records[0])
        assert candidate is not None
        assert candidate.project_slug == "unknown-project"


class TestInferKind:
    def test_coding_wins(self) -> None:
        assert infer_kind("anything", True) == "coding"

    def test_keyword_classes(self) -> None:
        assert infer_kind("Here is the research and prior art comparison.", False) == "research"
        assert infer_kind("Nothing notable here.", False) == "other"


class TestSelectReplayCandidates:
    def _mixed_archive(self, repo_root: Path) -> None:
        _write_archive(
            repo_root,
            [
                _record("archive/demo/plan1.md", sha="1" * 64, session="s1", messages=10, body=_planning_markdown()),
                _record("archive/demo/plan2.md", sha="2" * 64, session="s2", messages=12, body=_planning_markdown()),
                _record("archive/demo/code.md", sha="3" * 64, session="s3", messages=10, body=_coding_markdown()),
            ],
        )

    def test_selects_eligible_excludes_coding(self, repo_root: Path) -> None:
        self._mixed_archive(repo_root)
        selection = select_replay_candidates(_config(repo_root), limit=20)
        assert selection.scanned == 3
        assert len(selection.selected) == 2
        assert selection.excluded_hard == 1
        assert all(c.kind == "planning" for c in selection.selected)

    def test_limit_pushes_overflow_to_near_miss(self, repo_root: Path) -> None:
        self._mixed_archive(repo_root)
        selection = select_replay_candidates(_config(repo_root), limit=1)
        assert len(selection.selected) == 1
        assert len(selection.near_misses) == 1
        assert any("over selection limit" in reason for reason in selection.near_misses[0].exclusion_reasons)

    def test_kind_filter_moves_mismatches_to_near_miss(self, repo_root: Path) -> None:
        self._mixed_archive(repo_root)
        selection = select_replay_candidates(_config(repo_root), kind="research", limit=20)
        assert len(selection.selected) == 0
        assert len(selection.near_misses) == 2
        assert all(
            any("kind filter" in reason for reason in c.exclusion_reasons) for c in selection.near_misses
        )

    def test_deterministic_manifest_is_idempotent(self, repo_root: Path) -> None:
        self._mixed_archive(repo_root)
        first = render_manifest_jsonl(select_replay_candidates(_config(repo_root), limit=20))
        second = render_manifest_jsonl(select_replay_candidates(_config(repo_root), limit=20))
        assert first == second
        assert first.endswith("\n")

    def test_max_archive_records_caps_scan(self, repo_root: Path) -> None:
        self._mixed_archive(repo_root)
        selection = select_replay_candidates(_config(repo_root), limit=20, max_archive_records=1)
        assert selection.scanned == 1


class TestBaselineReplaySelect:
    def test_writes_manifest_without_excerpts(self, repo_root: Path) -> None:
        _write_archive(
            repo_root,
            [_record("archive/demo/plan.md", sha="1" * 64, session="s1", messages=10, body=_planning_markdown())],
        )
        assert baseline_replay_select(_config(repo_root), limit=20) == 0
        manifest = repo_root / "baseline" / "replay" / "manifest.jsonl"
        assert manifest.exists()
        entries = selected_manifest_entries(manifest)
        assert len(entries) == 1
        # Manifest must not leak transcript text.
        raw = manifest.read_text(encoding="utf-8")
        assert PLANNING_PROMPT not in raw
        assert "score" in entries[0] and "exclusion_reasons" in entries[0]

    def test_dry_run_does_not_write(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _write_archive(
            repo_root,
            [_record("archive/demo/plan.md", sha="1" * 64, session="s1", messages=10, body=_planning_markdown())],
        )
        assert baseline_replay_select(_config(repo_root), limit=20, dry_run=True) == 0
        assert "Would write" in capsys.readouterr().out
        assert not (repo_root / "baseline" / "replay" / "manifest.jsonl").exists()

    def test_requires_positive_limit(self, repo_root: Path) -> None:
        with pytest.raises(SystemExit):
            baseline_replay_select(_config(repo_root), limit=0)

    def test_relative_output_path(self, repo_root: Path) -> None:
        _write_archive(
            repo_root,
            [_record("archive/demo/plan.md", sha="1" * 64, session="s1", messages=10, body=_planning_markdown())],
        )
        assert baseline_replay_select(_config(repo_root), limit=20, output=Path("baseline/replay/m.jsonl")) == 0
        assert (repo_root / "baseline" / "replay" / "m.jsonl").exists()

    def test_no_index_writes_empty_manifest(self, repo_root: Path) -> None:
        assert baseline_replay_select(_config(repo_root), limit=20) == 0
        manifest = repo_root / "baseline" / "replay" / "manifest.jsonl"
        assert manifest.exists()
        assert manifest.read_text(encoding="utf-8") == ""
