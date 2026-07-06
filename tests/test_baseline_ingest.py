"""Tests for agent_sessions.baseline_ingest."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.baseline_ingest import (
    baseline_ingest,
    load_proposals,
    proposal_to_prediction,
    validate_proposal,
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