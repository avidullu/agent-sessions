"""Tests for agent_sessions.baseline_ingest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.baseline import load_baseline_settings
from agent_sessions.baseline_ingest import (
    archive_references,
    baseline_ingest,
    discover_proposal_paths,
    load_proposals,
    normalized_markdown_path,
    proposal_to_prediction,
    render_ingest_report,
    validate_proposal,
    write_ingest_artifacts,
)
from agent_sessions.config import ArchiveConfig

VALID_PROPOSAL = {
    "id": "guardrail.explicit-test-gates",
    "title": "Explicit Test Gates Before Done Claims",
    "scope": "global",
    "category": "regression-frameworks",
    "risk": "high",
    "confidence": 0.82,
    "approval_mode": "strict",
    "evidence": ["archive/example/session.md"],
    "suggested_baseline_text": "Run real gates before claiming done.",
    "open_questions": [],
}

ARCHIVE_RECORD = {
    "source": "codex-windows",
    "kind": "codex",
    "source_file": "C:/Users/alice/.codex/session.jsonl",
    "markdown": "archive\\codex-windows\\session.md",
    "metadata": {"session_id": "session-1"},
}

TRACE_PROPOSAL = {
    **VALID_PROPOSAL,
    "source_kind": "repo-handoff",
    "trace": [
        {
            "source": "baseline handoffs audit",
            "markdown_path": "archive/codex-windows/session.md",
            "session_id": "session-1",
            "project_slug": "agent-sessions",
        }
    ],
}


class TestValidateProposal:
    def test_normalized_markdown_path_only_removes_path_prefixes(self) -> None:
        assert normalized_markdown_path("./archive/codex/session.md") == "archive/codex/session.md"
        assert normalized_markdown_path("/archive/codex/session.md") == "archive/codex/session.md"
        assert normalized_markdown_path(".github/workflows/ci.yml") == ".github/workflows/ci.yml"

    def test_valid_proposal(self) -> None:
        assert validate_proposal(VALID_PROPOSAL) == []

    def test_missing_required_field(self) -> None:
        data = dict(VALID_PROPOSAL)
        del data["title"]
        errors = validate_proposal(data)
        assert any("title" in error for error in errors)

    def test_invalid_confidence(self) -> None:
        data = dict(VALID_PROPOSAL, confidence=1.5)
        errors = validate_proposal(data)
        assert any("confidence" in error for error in errors)

    def test_invalid_risk(self) -> None:
        data = dict(VALID_PROPOSAL, risk="critical")
        errors = validate_proposal(data)
        assert any("risk" in error for error in errors)

    def test_non_numeric_confidence(self) -> None:
        data = dict(VALID_PROPOSAL, confidence="high")
        errors = validate_proposal(data)
        assert any("numeric" in error for error in errors)

    def test_empty_required_field(self) -> None:
        data = dict(VALID_PROPOSAL, title="")
        errors = validate_proposal(data)
        assert any("title" in error for error in errors)

    def test_evidence_must_be_list(self) -> None:
        data = dict(VALID_PROPOSAL, evidence="not-a-list")
        errors = validate_proposal(data)
        assert any("evidence must be a list" in error for error in errors)

    def test_external_source_kind_requires_structured_trace(self) -> None:
        data = dict(VALID_PROPOSAL, source_kind="handoff")
        errors = validate_proposal(data, archive_references([ARCHIVE_RECORD]))
        assert any("must include structured trace" in error for error in errors)

    def test_trace_must_be_list_of_objects(self) -> None:
        data = dict(VALID_PROPOSAL, trace="not-a-list")
        assert validate_proposal(data) == ["trace must be a list"]
        data = dict(VALID_PROPOSAL, trace=["not-an-object"])
        errors = validate_proposal(data, archive_references([ARCHIVE_RECORD]))
        assert errors == ["trace[0] must be a JSON object"]

    def test_rejects_unresolved_trace_references(self) -> None:
        data = {
            **TRACE_PROPOSAL,
            "replay_of": "missing-session",
            "trace": [{"markdown_path": "archive/missing.md", "session_id": "missing-session"}],
        }
        errors = validate_proposal(data, archive_references([ARCHIVE_RECORD]))
        assert "unresolved replay_of `missing-session`" in errors
        assert "trace[0].markdown_path `archive/missing.md` does not resolve" in errors
        assert "trace[0].session_id `missing-session` does not resolve" in errors

    def test_resolves_trace_references_against_archive_index(self) -> None:
        errors = validate_proposal(TRACE_PROPOSAL, archive_references([ARCHIVE_RECORD]))
        assert errors == []


class TestDiscoverProposalPaths:
    def test_single_proposal_argument(self, tmp_path: Path) -> None:
        proposal = tmp_path / "one.json"
        proposal.write_text("{}", encoding="utf-8")
        assert discover_proposal_paths(tmp_path, proposal=proposal) == [proposal]

    def test_skips_schema_and_readme(self, tmp_path: Path) -> None:
        (tmp_path / "proposal.schema.json").write_text("{}", encoding="utf-8")
        (tmp_path / "README.md").write_text("# docs", encoding="utf-8")
        good = tmp_path / "guardrail.test.json"
        good.write_text("{}", encoding="utf-8")
        discovered = discover_proposal_paths(tmp_path)
        assert discovered == [good]


class TestLoadProposals:
    def test_accepts_valid_and_rejects_invalid(self, tmp_path: Path) -> None:
        good = tmp_path / "good.json"
        bad = tmp_path / "bad.json"
        good.write_text(json.dumps(VALID_PROPOSAL), encoding="utf-8")
        bad.write_text('{"id": "incomplete"}', encoding="utf-8")
        accepted, rejected = load_proposals([good, bad])
        assert len(accepted) == 1
        assert accepted[0].id == "guardrail.explicit-test-gates"
        assert len(rejected) == 1

    def test_rejects_invalid_json(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        accepted, rejected = load_proposals([broken])
        assert accepted == []
        assert len(rejected) == 1
        assert "invalid json" in rejected[0][1][0]

    def test_rejects_non_object_json(self, tmp_path: Path) -> None:
        array_file = tmp_path / "array.json"
        array_file.write_text("[]", encoding="utf-8")
        accepted, rejected = load_proposals([array_file])
        assert accepted == []
        assert rejected[0][1] == ["proposal must be a JSON object"]

    def test_rejects_external_proposal_without_archive_index(self, tmp_path: Path) -> None:
        proposal = tmp_path / "handoff.json"
        proposal.write_text(json.dumps(TRACE_PROPOSAL), encoding="utf-8")
        accepted, rejected = load_proposals([proposal])
        assert accepted == []
        assert rejected[0][1] == ["archive/index.jsonl missing; cannot validate trace references"]


class TestRenderIngestReport:
    def test_report_lists_accepted_and_rejected(self, tmp_path: Path) -> None:
        prediction = proposal_to_prediction(VALID_PROPOSAL)
        rejected = [(tmp_path / "bad.json", ["missing `title`"])]
        report = render_ingest_report([prediction], rejected, [tmp_path / "good.json", tmp_path / "bad.json"])
        assert "## Accepted Proposals" in report
        assert "guardrail.explicit-test-gates" in report
        assert "## Rejected Proposals" in report
        assert "bad.json" in report
        assert "missing `title`" in report


class TestWriteIngestArtifacts:
    def test_writes_report_and_sidecar(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        settings = load_baseline_settings(config)
        prediction = proposal_to_prediction(VALID_PROPOSAL)
        output = repo_root / "baseline" / "candidates" / "custom-ingest.md"
        report_path, sidecar_path = write_ingest_artifacts(
            settings,
            [prediction],
            "# Ingest report\n",
            output,
        )
        assert report_path == output
        assert sidecar_path == output.with_suffix(".predictions.json")
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert payload["run_id"] == "custom-ingest"
        assert payload["predictions"][0]["id"] == "guardrail.explicit-test-gates"

    def test_writes_trace_to_sidecar(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        settings = load_baseline_settings(config)
        prediction = proposal_to_prediction(TRACE_PROPOSAL)
        output = repo_root / "baseline" / "candidates" / "trace-ingest.md"
        _, sidecar_path = write_ingest_artifacts(settings, [prediction], "# Ingest report\n", output)
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert payload["predictions"][0]["trace"][0]["session_id"] == "session-1"


class TestBaselineIngest:
    def test_ingest_writes_candidate_artifacts(self, repo_root: Path) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "guardrail.test.json").write_text(
            json.dumps(VALID_PROPOSAL),
            encoding="utf-8",
        )
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(config)
        assert result == 0
        ingested = list((repo_root / "baseline" / "candidates").glob("*-ingested.md"))
        assert ingested
        sidecar = ingested[0].with_suffix(".predictions.json")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["source"] == "baseline ingest"
        assert payload["predictions"][0]["id"] == "guardrail.explicit-test-gates"

    def test_ingest_custom_output_writes_sidecar(self, repo_root: Path) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "guardrail.test.json").write_text(
            json.dumps(VALID_PROPOSAL),
            encoding="utf-8",
        )
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        output = repo_root / "tmp" / "pr16-ingested.md"
        result = baseline_ingest(config, output=output)
        assert result == 0
        assert output.exists()
        sidecar = output.with_suffix(".predictions.json")
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["candidate"].endswith("tmp/pr16-ingested.md")
        assert payload["predictions"][0]["id"] == "guardrail.explicit-test-gates"

    def test_ingest_validates_and_threads_trace_references(self, repo_root: Path) -> None:
        archive_dir = repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "index.jsonl").write_text(json.dumps(ARCHIVE_RECORD) + "\n", encoding="utf-8")
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "handoff.json").write_text(json.dumps(TRACE_PROPOSAL), encoding="utf-8")
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=archive_dir,
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(config)
        assert result == 0
        ingested = list((repo_root / "baseline" / "candidates").glob("*-ingested.md"))
        payload = json.loads(ingested[0].with_suffix(".predictions.json").read_text(encoding="utf-8"))
        assert payload["predictions"][0]["trace"][0]["markdown_path"] == "archive/codex-windows/session.md"

    def test_ingest_dry_run(self, repo_root: Path) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "guardrail.test.json").write_text(
            json.dumps(VALID_PROPOSAL),
            encoding="utf-8",
        )
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(config, dry_run=True)
        assert result == 0
        assert not list((repo_root / "baseline" / "candidates").glob("*-ingested.md"))

    def test_proposal_to_prediction(self) -> None:
        prediction = proposal_to_prediction(VALID_PROPOSAL)
        assert prediction.id == "guardrail.explicit-test-gates"
        assert prediction.feedback == "ingested"

    def test_ingest_relative_proposal_path(self, repo_root: Path) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "guardrail.test.json").write_text(
            json.dumps(VALID_PROPOSAL),
            encoding="utf-8",
        )
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(
            config,
            proposal=Path("baseline/proposals/guardrail.test.json"),
            dry_run=True,
        )
        assert result == 0

    def test_ingest_relative_output_path(self, repo_root: Path) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "guardrail.test.json").write_text(
            json.dumps(VALID_PROPOSAL),
            encoding="utf-8",
        )
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(config, output=Path("tmp/relative-ingest.md"))
        assert result == 0
        output = repo_root / "tmp" / "relative-ingest.md"
        assert output.exists()
        assert output.with_suffix(".predictions.json").exists()

    def test_ingest_no_proposals_found(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(config)
        assert result == 0
        captured = capsys.readouterr()
        assert "No proposal JSON files found" in captured.out

    def test_ingest_reports_skipped_invalid_files(
        self, repo_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / "guardrail.test.json").write_text(
            json.dumps(VALID_PROPOSAL),
            encoding="utf-8",
        )
        (proposals_dir / "broken.json").write_text("{bad", encoding="utf-8")
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_ingest(config)
        assert result == 0
        captured = capsys.readouterr()
        assert "Skipped 1 invalid proposal file(s)." in captured.out
