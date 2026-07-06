"""Calibration loop: apply feedback and ledger history to baseline predictions."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .baseline import Prediction, confidence, parse_verdict


LEDGER_ACCEPTED = "accepted-feedback"
LEDGER_REJECTED = "rejected-feedback"
LEDGER_EDIT = "edit-requested"


@dataclass(frozen=True)
class LedgerSummary:
    prediction_id: str
    total_runs: int
    accepted_runs: int
    rejected_runs: int
    edited_runs: int
    latest_status: str
    latest_confidence: float


def load_ledger_entries(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with ledger_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                entries.append(record)
    return entries


def summarize_ledger(entries: list[dict[str, Any]]) -> dict[str, LedgerSummary]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        prediction_id = str(entry.get("id", ""))
        if prediction_id:
            grouped.setdefault(prediction_id, []).append(entry)

    summaries: dict[str, LedgerSummary] = {}
    for prediction_id, records in grouped.items():
        statuses = Counter(str(record.get("status", "")) for record in records)
        latest = records[-1]
        summaries[prediction_id] = LedgerSummary(
            prediction_id=prediction_id,
            total_runs=len(records),
            accepted_runs=statuses.get(LEDGER_ACCEPTED, 0),
            rejected_runs=statuses.get(LEDGER_REJECTED, 0),
            edited_runs=statuses.get(LEDGER_EDIT, 0),
            latest_status=str(latest.get("status", "")),
            latest_confidence=float(latest.get("confidence", 0)),
        )
    return summaries


def feedback_verdict(feedback_map: dict[str, dict[str, str]], prediction_id: str) -> str:
    return parse_verdict(feedback_map.get(prediction_id))


def should_suppress_prediction(
    prediction: Prediction,
    feedback_map: dict[str, dict[str, str]],
    ledger_summary: LedgerSummary | None,
) -> bool:
    verdict = feedback_verdict(feedback_map, prediction.id)
    if verdict == "reject" or prediction.status == LEDGER_REJECTED:
        return True
    if ledger_summary and ledger_summary.rejected_runs >= 2:
        return True
    if ledger_summary and ledger_summary.latest_status == LEDGER_REJECTED and verdict == "reject":
        return True
    return False


def ledger_confidence_adjustment(ledger_summary: LedgerSummary | None) -> float:
    if ledger_summary is None:
        return 0.0
    adjustment = 0.0
    if ledger_summary.accepted_runs:
        adjustment += min(ledger_summary.accepted_runs, 3) * 0.02
    if ledger_summary.rejected_runs:
        adjustment -= min(ledger_summary.rejected_runs, 3) * 0.04
    if ledger_summary.edited_runs:
        adjustment -= min(ledger_summary.edited_runs, 2) * 0.02
    return adjustment


def apply_ledger_note(prediction: Prediction, ledger_summary: LedgerSummary | None) -> str:
    if ledger_summary is None:
        return prediction.feedback
    note = (
        f"ledger: {ledger_summary.total_runs} runs "
        f"(accept={ledger_summary.accepted_runs}, reject={ledger_summary.rejected_runs}, edit={ledger_summary.edited_runs})"
    )
    if prediction.feedback and prediction.feedback != "none":
        return f"{prediction.feedback}; {note}"
    return note


def apply_calibration_loop(
    predictions: list[Prediction],
    feedback_map: dict[str, dict[str, str]],
    ledger_entries: list[dict[str, Any]],
) -> list[Prediction]:
    summaries = summarize_ledger(ledger_entries)
    calibrated: list[Prediction] = []
    for prediction in predictions:
        summary = summaries.get(prediction.id)
        if should_suppress_prediction(prediction, feedback_map, summary):
            continue
        updated = prediction
        adjustment = ledger_confidence_adjustment(summary)
        if adjustment:
            updated = replace(updated, confidence=confidence(updated.confidence + adjustment))
        updated = replace(updated, feedback=apply_ledger_note(updated, summary))
        calibrated.append(updated)
    return calibrated


def calibration_delta(
    before: list[Prediction],
    after: list[Prediction],
) -> dict[str, Any]:
    before_by_id = {prediction.id: prediction for prediction in before}
    after_by_id = {prediction.id: prediction for prediction in after}
    suppressed = sorted(set(before_by_id) - set(after_by_id))
    confidence_changes = {
        prediction_id: round(after_by_id[prediction_id].confidence - before_by_id[prediction_id].confidence, 4)
        for prediction_id in after_by_id
        if prediction_id in before_by_id
        and after_by_id[prediction_id].confidence != before_by_id[prediction_id].confidence
    }
    return {
        "suppressed_ids": suppressed,
        "confidence_changes": confidence_changes,
        "before_count": len(before),
        "after_count": len(after),
    }