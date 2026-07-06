"""Tests for agent_sessions.baseline_ingest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.baseline_ingest import (
    baseline_ingest,
    discover_proposal_paths,
    load_proposals,
    proposal_to_prediction,
    render_ingest_report,
    validate_proposal,
    write_ingest_artifacts,
)
from agent_sessions.baseline import load_baseline_settings
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


class TestValidateProposal:
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