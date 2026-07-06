"""Tests for agent_sessions.baseline_calibration."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.baseline import Prediction, apply_feedback
from agent_sessions.baseline_calibration import (
    apply_calibration_loop,
    apply_ledger_note,
    calibration_delta,
    feedback_verdict,
    ledger_confidence_adjustment,
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

    def test_apply_calibration_loop_does_not_mutate_input(self) -> None:
        prediction = _prediction("guardrail.pr-only-repo-writes", confidence=0.7)
        feedback = {"guardrail.pr-only-repo-writes": {"verdict": "accept", "note": "Good."}}
        prediction = apply_feedback(prediction, feedback)
        before_confidence = prediction.confidence
        before_feedback = prediction.feedback
        ledger = [
            {"id": "guardrail.pr-only-repo-writes", "status": "accepted-feedback", "confidence": 0.9},
            {"id": "guardrail.pr-only-repo-writes", "status": "accepted-feedback", "confidence": 0.92},
        ]
        calibrated = apply_calibration_loop([prediction], feedback, ledger)
        delta = calibration_delta([prediction], calibrated)
        assert prediction.confidence == before_confidence
        assert prediction.feedback == before_feedback
        assert delta["confidence_changes"]["guardrail.pr-only-repo-writes"] > 0

    def test_load_ledger_skips_blank_lines(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            "\n"
            + json.dumps({"id": "guardrail.one", "status": "accepted-feedback", "confidence": 0.8})
            + "\n\n",
            encoding="utf-8",
        )
        entries = load_ledger_entries(ledger)
        assert len(entries) == 1

    def test_feedback_verdict_and_suppress_helpers(self) -> None:
        prediction = _prediction("guardrail.stale")
        feedback = {"guardrail.stale": {"verdict": "reject", "note": "No."}}
        summary = summarize_ledger(
            [
                {"id": "guardrail.stale", "status": "rejected-feedback", "confidence": 0.4},
            ]
        )["guardrail.stale"]
        assert feedback_verdict(feedback, "guardrail.stale") == "reject"
        assert should_suppress_prediction(prediction, feedback, summary) is True
        assert ledger_confidence_adjustment(summary) < 0

    def test_apply_ledger_note_appends_existing_feedback(self) -> None:
        prediction = _prediction("guardrail.one")
        prediction.feedback = "accept: yes"
        summary = summarize_ledger(
            [{"id": "guardrail.one", "status": "accepted-feedback", "confidence": 0.8}]
        )["guardrail.one"]
        note = apply_ledger_note(prediction, summary)
        assert note.startswith("accept: yes; ledger:")

    def test_apply_ledger_note_without_prior_feedback(self) -> None:
        prediction = _prediction("guardrail.one")
        summary = summarize_ledger(
            [{"id": "guardrail.one", "status": "edit-requested", "confidence": 0.6}]
        )["guardrail.one"]
        note = apply_ledger_note(prediction, summary)
        assert note.startswith("ledger:")
        assert ledger_confidence_adjustment(summary) < 0