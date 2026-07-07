"""Shared baseline datatypes and pure helpers.

This module has no imports from other baseline modules, so both `baseline`
and `baseline_calibration` (and every other sibling) can depend on it without
creating an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Pilot:
    slug: str
    kind: str
    aliases: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class BaselineSettings:
    root: Path
    candidates_dir: Path
    metacognition_dir: Path
    ledger_path: Path
    feedback_example: Path
    pilots: tuple[Pilot, ...]


@dataclass(frozen=True)
class Prediction:
    id: str
    title: str
    scope: str
    risk: str
    category: str
    confidence: float
    status: str
    evidence: list[str]
    text: str
    trace: tuple[dict[str, str], ...] = ()
    feedback: str = "none"


@dataclass(frozen=True)
class TextSignal:
    source: str
    markdown: str
    count: int


def confidence(value: float) -> float:
    return max(0.01, min(0.99, value))


def parse_verdict(feedback_item: dict[str, str] | None) -> str:
    """Normalize a feedback entry's verdict to a lowercased string ("" if absent).

    The single canonical parse for accept/edit/reject verdicts, shared by every
    consumer instead of re-implementing ``str(item.get("verdict","")).strip().lower()``.
    """
    if not feedback_item:
        return ""
    return str(feedback_item.get("verdict", "")).strip().lower()


def prediction_to_dict(prediction: Prediction) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": prediction.id,
        "title": prediction.title,
        "scope": prediction.scope,
        "risk": prediction.risk,
        "category": prediction.category,
        "confidence": round(prediction.confidence, 4),
        "status": prediction.status,
        "feedback": prediction.feedback,
        "evidence": prediction.evidence,
        "text": prediction.text,
    }
    if prediction.trace:
        result["trace"] = [dict(item) for item in prediction.trace]
    return result
