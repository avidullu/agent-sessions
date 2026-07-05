"""Tests for agent_sessions.baseline_calibration."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.baseline import Prediction, apply_feedback
from agent_sessions.baseline_calibration import (
    apply_calibration_loop,
    calibration_delta,
    load_ledger_entries,
    should_suppress_prediction,
    summarize_ledger,
)


def _prediction(prediction_id: str, status: str = "proposed", confidence: float = 0.6) -> Prediction:
    return Prediction(
        id=prediction_id,
        title=prediction_id,
        scope="global",
        risk="medium",
        category="docs",
        confidence=confidence,
        status=status,
        evidence=[],
        text="text",
    )


class TestLedgerSummary:
    def test_summarize_ledger(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            json.dumps({"id": "guardrail.one", "status": "accepted-feedback", "confidence": 0.8})
            + "\n"
            + json.dumps({"id": "guardrail.one", "status": "rejected-feedback", "confidence": 0.4})
            + "\n",
            encoding="utf-8",
        )
        summaries = summarize_ledger(load_ledger_entries(ledger))
        assert summaries["guardrail.one"].total_runs == 2
        assert summaries["guardrail.one"].accepted_runs == 1
        assert summaries["guardrail.one"].rejected_runs == 1


class TestCalibrationLoop:
    def test_suppresses_feedback_rejected(self) -> None:
        predictions = [
            _prediction("profile.business-productivity-engineer"),
            _prediction("guardrail.pr-only-repo-writes"),
        ]
        feedback = {
            "profile.business-productivity-engineer": {"verdict": "reject", "note": "No."},
            "guardrail.pr-only-repo-writes": {"verdict": "accept", "note": "Yes."},
        }
        predictions = [apply_feedback(prediction, feedback) for prediction in predictions]
        calibrated = apply_calibration_loop(predictions, feedback, [])
        ids = {prediction.id for prediction in calibrated}
        assert "profile.business-productivity-engineer" not in ids
        assert "guardrail.pr-only-repo-writes" in ids

    def test_suppresses_after_two_ledger_rejections(self) -> None:
        prediction = _prediction("guardrail.stale-rule")
        feedback: dict[str, dict[str, str]] = {}
        ledger = [
            {"id": "guardrail.stale-rule", "status": "rejected-feedback", "confidence": 0.4},
            {"id": "guardrail.stale-rule", "status": "rejected-feedback", "confidence": 0.3},
        ]
        assert should_suppress_prediction(prediction, feedback, summarize_ledger(ledger)["guardrail.stale-rule"])
        calibrated = apply_calibration_loop([prediction], feedback, ledger)
        assert calibrated == []

    def test_ledger_adjusts_confidence_and_note(self) -> None:
        prediction = _prediction("guardrail.pr-only-repo-writes", confidence=0.7)
        feedback = {"guardrail.pr-only-repo-writes": {"verdict": "accept", "note": "Good."}}
        prediction = apply_feedback(prediction, feedback)
        before = prediction.confidence
        ledger = [
            {"id": "guardrail.pr-only-repo-writes", "status": "accepted-feedback", "confidence": 0.9},
            {"id": "guardrail.pr-only-repo-writes", "status": "accepted-feedback", "confidence": 0.92},
        ]
        calibrated = apply_calibration_loop([prediction], feedback, ledger)
        assert len(calibrated) == 1
        assert calibrated[0].confidence > before
        assert "ledger:" in calibrated[0].feedback

    def test_calibration_delta_reports_changes(self) -> None:
        before = [_prediction("a"), _prediction("b")]
        after = [_prediction("a", confidence=0.8)]
        delta = calibration_delta(before, after)
        assert delta["suppressed_ids"] == ["b"]
        assert "a" in delta["confidence_changes"]