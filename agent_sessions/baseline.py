"""Baseline orchestration: scaffold, suggest, and calibrate commands.

The baseline subsystem is split into focused modules; this one keeps the
top-level commands and the prediction-artifact IO, and re-exports the public
API so existing ``from agent_sessions.baseline import ...`` call sites keep
working:

- ``baseline_types``       — shared dataclasses + pure helpers (cycle-free root)
- ``baseline_settings``    — settings loading, scaffold templates, feedback IO
- ``baseline_predictions`` — keyword scanning + deterministic predictions
- ``baseline_report``      — candidate/calibration Markdown rendering
- ``baseline_promote``     — marker blocks + promotion of accepted guardrails
- ``baseline_calibration`` — feedback/ledger calibration loop
"""

from __future__ import annotations

import datetime as dt
import json
import os
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from .baseline_calibration import apply_calibration_loop, load_ledger_entries
from .baseline_predictions import (
    KEYWORD_GROUPS,
    PR_ONLY_REPO_WRITES_TEXT,
    build_predictions,
    keyword_hits,
    project_evidence,
    project_signal_counts,
    scan_text_signals,
    signal_confidence,
    signal_evidence,
    tracked_project_doc_confidence,
    tracked_project_doc_evidence,
)
from .baseline_promote import (
    PROMOTED_PLACEHOLDER,
    PROMOTION_BEGIN,
    PROMOTION_END,
    baseline_promote,
    category_promotion_target,
    global_baseline_header,
    parse_promoted_blocks,
    promote_predictions,
    render_promoted_block,
    select_promotable_predictions,
    upsert_promoted_content,
)
from .baseline_report import (
    render_calibration_summary,
    render_candidate_report,
    render_id_list,
    render_prediction,
)
from .baseline_settings import (
    BASELINE_CONFIG,
    BASELINE_ROOT,
    agent_readme,
    baseline_files,
    baseline_readme,
    candidates_readme,
    feedback_example,
    load_baseline_settings,
    load_feedback,
    metacognition_readme,
    project_readme,
    resolve_prediction_sidecar,
)
from .baseline_types import (
    BaselineSettings,
    Pilot,
    Prediction,
    TextSignal,
    confidence,
    parse_verdict,
    prediction_to_dict,
)
from .config import ArchiveConfig
from .utils import read_jsonl_dicts

__all__ = [
    # orchestration commands (this module)
    "baseline_scaffold",
    "baseline_suggest",
    "baseline_calibrate",
    "load_index_records",
    "apply_feedback",
    "write_prediction_artifacts",
    "upsert_ledger",
    "is_relative_to",
    # baseline_types
    "Pilot",
    "BaselineSettings",
    "Prediction",
    "TextSignal",
    "confidence",
    "parse_verdict",
    "prediction_to_dict",
    # baseline_settings
    "BASELINE_CONFIG",
    "BASELINE_ROOT",
    "load_baseline_settings",
    "load_feedback",
    "resolve_prediction_sidecar",
    "baseline_files",
    "baseline_readme",
    "candidates_readme",
    "agent_readme",
    "project_readme",
    "feedback_example",
    "metacognition_readme",
    # baseline_predictions
    "KEYWORD_GROUPS",
    "PR_ONLY_REPO_WRITES_TEXT",
    "project_signal_counts",
    "scan_text_signals",
    "keyword_hits",
    "build_predictions",
    "signal_confidence",
    "project_evidence",
    "signal_evidence",
    "tracked_project_doc_confidence",
    "tracked_project_doc_evidence",
    # baseline_report
    "render_candidate_report",
    "render_prediction",
    "render_calibration_summary",
    "render_id_list",
    # baseline_promote
    "PROMOTION_BEGIN",
    "PROMOTION_END",
    "PROMOTED_PLACEHOLDER",
    "category_promotion_target",
    "parse_promoted_blocks",
    "render_promoted_block",
    "global_baseline_header",
    "upsert_promoted_content",
    "select_promotable_predictions",
    "promote_predictions",
    "baseline_promote",
]


def baseline_scaffold(config: ArchiveConfig, dry_run: bool = False) -> int:
    settings = load_baseline_settings(config)
    files = baseline_files(settings)
    for path, content in files.items():
        if dry_run:
            print(f"Would ensure {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Baseline scaffold {'checked' if dry_run else 'ready'} at {settings.root}.")
    return 0


def baseline_suggest(
    config: ArchiveConfig,
    output: Path | None = None,
    max_sessions: int = 500,
    feedback: Path | None = None,
    dry_run: bool = False,
    use_calibration: bool = True,
) -> int:
    settings = load_baseline_settings(config)
    index_records = load_index_records(config)
    feedback_map = load_feedback(config, feedback)
    source_counts = Counter(str(record.get("source", "")) for record in index_records)
    kind_counts = Counter(str(record.get("kind", "")) for record in index_records)
    project_hits = project_signal_counts(settings, index_records)
    text_signals = scan_text_signals(config, index_records, max_sessions=max_sessions)
    predictions = build_predictions(
        settings=settings,
        source_counts=source_counts,
        kind_counts=kind_counts,
        project_hits=project_hits,
        text_signals=text_signals,
    )
    predictions = [apply_feedback(prediction, feedback_map) for prediction in predictions]
    if use_calibration:
        predictions = apply_calibration_loop(
            predictions,
            feedback_map,
            load_ledger_entries(settings.ledger_path),
        )
    markdown = render_candidate_report(
        settings=settings,
        index_records=index_records,
        source_counts=source_counts,
        kind_counts=kind_counts,
        project_hits=project_hits,
        text_signals=text_signals,
        predictions=predictions,
        max_sessions=max_sessions,
        feedback_path=feedback,
    )
    target = output or settings.candidates_dir / f"{dt.date.today().isoformat()}-extraction.md"
    if not target.is_absolute():
        target = config.repo_root / target
    if dry_run:
        print(markdown)
        print(f"Would write {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    if is_relative_to(target, settings.candidates_dir):
        write_prediction_artifacts(
            settings=settings,
            candidate_path=target,
            predictions=predictions,
            source_counts=source_counts,
            kind_counts=kind_counts,
            project_hits=project_hits,
            scanned_sessions=len(index_records) if max_sessions == 0 else min(max_sessions, len(index_records)),
        )
    print(f"Wrote {target}")
    return 0


def baseline_calibrate(
    config: ArchiveConfig,
    feedback: Path,
    predictions: Path | None = None,
    output: Path | None = None,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    feedback_map = load_feedback(config, feedback)
    prediction_path = resolve_prediction_sidecar(settings, predictions)
    prediction_data = json.loads(prediction_path.read_text(encoding="utf-8"))
    summary = render_calibration_summary(prediction_data, feedback_map, feedback, prediction_path)
    target = output or settings.metacognition_dir / "calibration-summary.md"
    if not target.is_absolute():
        target = config.repo_root / target
    if dry_run:
        print(summary)
        print(f"Would write {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary, encoding="utf-8", newline="\n")
    print(f"Wrote {target}")
    return 0


def load_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    index_path = config.archive_dir / "index.jsonl"
    if not index_path.exists():
        raise SystemExit("archive/index.jsonl does not exist. Run export first.")
    return read_jsonl_dicts(index_path, label="archive/index.jsonl")


def apply_feedback(prediction: Prediction, feedback_map: dict[str, dict[str, str]]) -> Prediction:
    item = feedback_map.get(prediction.id)
    if not item:
        return prediction
    verdict = parse_verdict(item)
    note = str(item.get("note", "")).strip()
    status, adjusted = prediction.status, prediction.confidence
    if verdict == "accept":
        status = "accepted-feedback"
        adjusted = min(0.99, prediction.confidence + 0.08)
    elif verdict == "reject":
        status = "rejected-feedback"
        adjusted = max(0.01, prediction.confidence - 0.35)
    elif verdict == "edit":
        status = "edit-requested"
        adjusted = max(0.01, prediction.confidence - 0.08)
    feedback = f"{verdict}: {note}" if note else verdict or "present"
    return replace(prediction, status=status, confidence=adjusted, feedback=feedback)


def write_prediction_artifacts(
    settings: BaselineSettings,
    candidate_path: Path,
    predictions: list[Prediction],
    source_counts: Counter[str],
    kind_counts: Counter[str],
    project_hits: Counter[str],
    scanned_sessions: int,
) -> None:
    run_id = candidate_path.stem
    payload = {
        "run_id": run_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "candidate": str(candidate_path.relative_to(settings.root.parent)).replace("\\", "/"),
        "scanned_sessions": scanned_sessions,
        "source_counts": dict(source_counts),
        "kind_counts": dict(kind_counts),
        "project_hits": dict(project_hits),
        "predictions": [prediction_to_dict(prediction) for prediction in predictions],
    }
    sidecar = candidate_path.with_suffix(".predictions.json")
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    upsert_ledger(settings.ledger_path, run_id, cast(list[dict[str, Any]], payload["predictions"]))


def upsert_ledger(ledger_path: Path, run_id: str, predictions: list[dict[str, Any]]) -> None:
    existing: list[dict[str, Any]] = []
    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("run_id") != run_id:
                    existing.append(record)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    recorded_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    lines = [json.dumps(record, ensure_ascii=False) for record in existing]
    for prediction in predictions:
        record = {"run_id": run_id, "recorded_at": recorded_at, **prediction}
        lines.append(json.dumps(record, ensure_ascii=False))
    # Write atomically: a crash mid-write must not truncate or corrupt the
    # ledger the calibration loop depends on. Write a sibling temp file, then
    # os.replace() (atomic on the same filesystem).
    tmp_path = ledger_path.parent / f"{ledger_path.name}.{os.getpid()}.tmp"
    tmp_path.write_text("".join(line + "\n" for line in lines), encoding="utf-8", newline="\n")
    os.replace(tmp_path, ledger_path)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True
