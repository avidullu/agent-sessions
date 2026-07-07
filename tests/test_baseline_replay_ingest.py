"""Tests for external replay-result ingest (K11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.baseline_ingest import load_archive_references, validate_proposal
from agent_sessions.baseline_replay_ingest import (
    baseline_replay_ingest,
    numeric_confidence,
    replay_result_to_proposal,
    session_markdown_map,
    validate_replay_result,
)
from agent_sessions.config import ArchiveConfig


def _config(repo_root: Path) -> ArchiveConfig:
    return ArchiveConfig(repo_root=repo_root, archive_dir=repo_root / "archive", raw_dir=repo_root / "raw", sources=())


ARCHIVE_RECORD = {
    "source": "codex-windows",
    "kind": "codex",
    "sha256": "a" * 64,
    "messages": 10,
    "markdown": "archive\\codex-windows\\session.md",
    "metadata": {"session_id": "session-1"},
}


def _write_archive(repo_root: Path) -> None:
    archive = repo_root / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "index.jsonl").write_text(json.dumps(ARCHIVE_RECORD) + "\n", encoding="utf-8")


def _result(**overrides: object) -> dict:
    data = {
        "replay_of": "session-1",
        "replayer": "grok (different lineage)",
        "rubric_version": "replay-rubric-v1",
        "claim": "The plan should name explicit rollback steps for each phase.",
        "evidence": ["original:excerpt-3", "replay:output-1"],
        "confidence": 0.7,
        "recommended_action": "proposal",
    }
    data.update(overrides)
    return data


class TestValidation:
    def test_valid_result_passes(self, repo_root: Path) -> None:
        _write_archive(repo_root)
        refs = load_archive_references(_config(repo_root))
        assert refs is not None
        assert validate_replay_result(_result(), refs.session_ids) == []

    def test_unresolved_replay_of_rejected(self, repo_root: Path) -> None:
        _write_archive(repo_root)
        refs = load_archive_references(_config(repo_root))
        assert refs is not None
        errors = validate_replay_result(_result(replay_of="ghost"), refs.session_ids)
        assert any("unresolved replay_of" in e for e in errors)

    def test_missing_and_bad_fields(self, repo_root: Path) -> None:
        errors = validate_replay_result(
            {"replay_of": "session-1", "recommended_action": "delete", "confidence": 5}, frozenset({"session-1"})
        )
        assert any("missing `claim`" in e for e in errors)
        assert any("invalid recommended_action" in e for e in errors)
        assert any("confidence must be" in e for e in errors)

    def test_numeric_confidence_enum_and_bounds(self) -> None:
        assert numeric_confidence("high") == 0.8
        assert numeric_confidence(0.5) == 0.5
        assert numeric_confidence(1.5) is None
        assert numeric_confidence("nope") is None


class TestProposalConversion:
    def test_generated_proposal_passes_k5_validation(self, repo_root: Path) -> None:
        _write_archive(repo_root)
        refs = load_archive_references(_config(repo_root))
        smap = session_markdown_map([ARCHIVE_RECORD])
        proposal = replay_result_to_proposal(_result(), smap)
        assert proposal["source_kind"] == "replay"
        assert proposal["replay_of"] == "session-1"
        # The whole point of K11: the generated proposal clears the K5 ingest gate.
        assert validate_proposal(proposal, refs) == []

    def test_enum_confidence_maps_to_number(self, repo_root: Path) -> None:
        smap = session_markdown_map([ARCHIVE_RECORD])
        proposal = replay_result_to_proposal(_result(confidence="medium"), smap)
        assert proposal["confidence"] == 0.6


class TestBaselineReplayIngest:
    def _run(self, repo_root: Path, results: object) -> int:
        _write_archive(repo_root)
        result_path = repo_root / "result.json"
        result_path.write_text(json.dumps(results), encoding="utf-8")
        return baseline_replay_ingest(_config(repo_root), result=result_path)

    def test_proposal_result_writes_proposal_and_ledger(self, repo_root: Path) -> None:
        rc = self._run(repo_root, _result())
        assert rc == 0
        proposals = list((repo_root / "baseline" / "proposals").glob("replay.*.json"))
        assert len(proposals) == 1
        ledger = repo_root / "baseline" / "replay" / "ledger.jsonl"
        assert ledger.exists()
        record = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert record["resolved"] is True and record["proposal_id"]

    def test_watchlist_result_ledger_only(self, repo_root: Path) -> None:
        rc = self._run(repo_root, _result(recommended_action="watchlist"))
        assert rc == 0
        assert not list((repo_root / "baseline" / "proposals").glob("replay.*.json"))
        assert (repo_root / "baseline" / "replay" / "ledger.jsonl").exists()

    def test_unresolved_result_rejected_and_recorded(self, repo_root: Path) -> None:
        rc = self._run(repo_root, _result(replay_of="ghost"))
        assert rc == 1  # non-zero on rejection
        assert not list((repo_root / "baseline" / "proposals").glob("replay.*.json"))
        record = json.loads((repo_root / "baseline" / "replay" / "ledger.jsonl").read_text(encoding="utf-8").strip())
        assert record["resolved"] is False
        assert any("unresolved replay_of" in r for r in record["reasons"])

    def test_ledger_is_append_only_across_runs(self, repo_root: Path) -> None:
        self._run(repo_root, _result())
        result2 = repo_root / "result2.json"
        result2.write_text(json.dumps(_result(replay_of="session-1", claim="A second distinct lesson.")), encoding="utf-8")
        baseline_replay_ingest(_config(repo_root), result=result2)
        lines = [line for line in (repo_root / "baseline" / "replay" / "ledger.jsonl").read_text().splitlines() if line]
        assert len(lines) == 2

    def test_refuses_to_overwrite_human_proposal(self, repo_root: Path) -> None:
        _write_archive(repo_root)
        proposal_id = replay_result_to_proposal(_result(), session_markdown_map([ARCHIVE_RECORD]))["id"]
        proposals_dir = repo_root / "baseline" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        (proposals_dir / f"{proposal_id}.json").write_text('{"id": "hand"}', encoding="utf-8")
        result_path = repo_root / "result.json"
        result_path.write_text(json.dumps(_result()), encoding="utf-8")
        with pytest.raises(SystemExit):
            baseline_replay_ingest(_config(repo_root), result=result_path)

    def test_list_of_results_mixed_actions(self, repo_root: Path) -> None:
        results = [
            _result(claim="Lesson one about rollback steps."),
            _result(claim="Lesson two.", recommended_action="watchlist"),
            _result(replay_of="ghost", claim="Unresolved."),
        ]
        rc = self._run(repo_root, results)
        assert rc == 1  # one rejected
        proposals = list((repo_root / "baseline" / "proposals").glob("replay.*.json"))
        assert len(proposals) == 1  # only the "proposal" action with a resolvable session
        lines = [line for line in (repo_root / "baseline" / "replay" / "ledger.jsonl").read_text().splitlines() if line]
        assert len(lines) == 3  # every result recorded in the ledger

    def test_missing_result_raises(self, repo_root: Path) -> None:
        with pytest.raises(SystemExit):
            baseline_replay_ingest(_config(repo_root))

    def test_dry_run_writes_nothing(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _write_archive(repo_root)
        result_path = repo_root / "result.json"
        result_path.write_text(json.dumps(_result()), encoding="utf-8")
        assert baseline_replay_ingest(_config(repo_root), result=result_path, dry_run=True) == 0
        assert "Replay ingest:" in capsys.readouterr().out
        assert not (repo_root / "baseline" / "replay" / "ledger.jsonl").exists()
        assert not list((repo_root / "baseline" / "proposals").glob("replay.*.json"))
