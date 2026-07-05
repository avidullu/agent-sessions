"""Programmatic efficacy gate evaluation for the baseline loop."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .baseline import (
    PROMOTED_PLACEHOLDER,
    apply_feedback,
    build_predictions,
    load_baseline_settings,
    load_feedback,
    parse_promoted_blocks,
)
from .baseline_calibration import apply_calibration_loop, calibration_delta, load_ledger_entries
from .config import ArchiveConfig, read_toml


@dataclass(frozen=True)
class EfficacyCheck:
    metric_id: str
    phase: str
    status: str
    detail: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _latest_sidecar(candidates_dir: Path) -> Path | None:
    sidecars = sorted(candidates_dir.glob("*.predictions.json"), key=lambda item: item.stat().st_mtime)
    return sidecars[-1] if sidecars else None


def evaluate_e1_detect(repo_root: Path) -> EfficacyCheck:
    candidates_dir = repo_root / "baseline" / "candidates"
    sidecar = _latest_sidecar(candidates_dir)
    if sidecar is None:
        return EfficacyCheck("E1.detect.tracked-project-template", "detect", "fail", "No prediction sidecar found.")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    predictions = data.get("predictions", [])
    tracked = next((item for item in predictions if item.get("id") == "guardrail.tracked-project-docs"), None)
    if tracked is None:
        return EfficacyCheck("E1.detect.tracked-project-template", "detect", "fail", "Missing guardrail.tracked-project-docs.")
    evidence = tracked.get("evidence", [])
    if not evidence:
        return EfficacyCheck("E1.detect.tracked-project-template", "detect", "fail", "Tracked-project-docs has no evidence.")
    return EfficacyCheck(
        "E1.detect.tracked-project-template",
        "detect",
        "pass",
        f"Found guardrail.tracked-project-docs with confidence {tracked.get('confidence')}.",
    )


def evaluate_e2_anchor(repo_root: Path) -> EfficacyCheck:
    config_path = repo_root / "config" / "baseline.toml"
    data = read_toml(config_path) if config_path.exists() else {}
    anchors = data.get("calibration_anchors", [])
    template_anchor = next(
        (
            anchor
            for anchor in anchors
            if anchor.get("kind") == "tracked-project-doc"
            and anchor.get("source_repo") == "badminton-highlight-indexer"
        ),
        None,
    )
    if template_anchor is None:
        return EfficacyCheck("E2.anchor.template-source", "anchor", "fail", "Template calibration anchor missing.")
    return EfficacyCheck(
        "E2.anchor.template-source",
        "anchor",
        "pass",
        f"Anchor links {template_anchor.get('source_repo')}/{template_anchor.get('source_path')}.",
    )


def evaluate_e3_dogfood(repo_root: Path) -> EfficacyCheck:
    doc = repo_root / "docs" / "BASELINE_LOOP_CLOSURE.md"
    text = _read_text(doc)
    if not text or "§7" not in text and "progress tracker" not in text.lower():
        return EfficacyCheck("E3.dogfood.tracked-project-doc", "dogfood", "fail", "BASELINE_LOOP_CLOSURE tracker missing.")
    if "P0" not in text or "P9" not in text:
        return EfficacyCheck("E3.dogfood.tracked-project-doc", "dogfood", "fail", "P0-P9 tracker rows missing.")
    return EfficacyCheck("E3.dogfood.tracked-project-doc", "dogfood", "pass", "Tracked project doc with §7 rows present.")


def evaluate_e4_promote(repo_root: Path) -> EfficacyCheck:
    path = repo_root / "baseline" / "global" / "engineering-guardrails.md"
    text = _read_text(path)
    if PROMOTED_PLACEHOLDER in text:
        return EfficacyCheck("E4.promote.global-baseline", "promote", "fail", "Global guardrails still placeholder.")
    blocks = parse_promoted_blocks(text)
    if not blocks:
        return EfficacyCheck("E4.promote.global-baseline", "promote", "fail", "No promoted guardrail blocks found.")
    return EfficacyCheck(
        "E4.promote.global-baseline",
        "promote",
        "pass",
        f"{len(blocks)} promoted guardrail block(s) in engineering-guardrails.md.",
    )


def evaluate_e5_publish(repo_root: Path) -> EfficacyCheck:
    path = repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md"
    if not path.exists():
        return EfficacyCheck("E5.publish.agent-slices", "publish", "fail", "CLAUDE.generated.md missing.")
    lines = path.read_text(encoding="utf-8").splitlines()
    rule_count = sum(1 for line in lines if line.startswith("### "))
    if len(lines) <= 20 or rule_count < 3:
        return EfficacyCheck(
            "E5.publish.agent-slices",
            "publish",
            "fail",
            f"CLAUDE.generated.md too small (lines={len(lines)}, rules={rule_count}).",
        )
    return EfficacyCheck(
        "E5.publish.agent-slices",
        "publish",
        "pass",
        f"CLAUDE.generated.md has {rule_count} rules across {len(lines)} lines.",
    )


def evaluate_e6_calibrate(repo_root: Path) -> EfficacyCheck:
    feedback_path = repo_root / "baseline" / "calibration" / "feedback.example.toml"
    if not feedback_path.exists():
        return EfficacyCheck("E6.calibrate.feedback-loop", "calibrate", "fail", "feedback.example.toml missing.")

    config = ArchiveConfig(
        repo_root=repo_root,
        archive_dir=repo_root / "archive",
        raw_dir=repo_root / "raw",
        sources=(),
    )
    settings = load_baseline_settings(config)
    feedback_map = load_feedback(config, feedback_path)
    ledger_entries = load_ledger_entries(settings.ledger_path)

    base_predictions = build_predictions(
        settings=settings,
        source_counts=Counter({"claude": 3}),
        kind_counts=Counter({"claude": 3}),
        project_hits=Counter(),
        text_signals={
            "tracked-project-docs": [],
            "repo-governance": [],
            "regression-frameworks": [],
            "checkpointing": [],
            "metacognition": [],
        },
    )
    feedback_applied = [apply_feedback(prediction, feedback_map) for prediction in base_predictions]
    calibrated = apply_calibration_loop(feedback_applied, feedback_map, ledger_entries)
    delta = calibration_delta(feedback_applied, calibrated)

    rejected_ids = [
        prediction_id
        for prediction_id, item in feedback_map.items()
        if str(item.get("verdict", "")).strip().lower() == "reject"
    ]
    suppressed_rejected = all(prediction_id in delta["suppressed_ids"] for prediction_id in rejected_ids)
    accepted_ids = [
        prediction_id
        for prediction_id, item in feedback_map.items()
        if str(item.get("verdict", "")).strip().lower() == "accept"
    ]
    accepted_present = all(
        any(prediction.id == prediction_id for prediction in calibrated) for prediction_id in accepted_ids
    )
    confidence_moved = bool(delta["confidence_changes"]) or any(
        prediction.feedback != "none" for prediction in calibrated
    )

    if not suppressed_rejected:
        return EfficacyCheck(
            "E6.calibrate.feedback-loop",
            "calibrate",
            "fail",
            f"Rejected ids not suppressed: {rejected_ids} vs {delta['suppressed_ids']}.",
        )
    if not accepted_present:
        return EfficacyCheck("E6.calibrate.feedback-loop", "calibrate", "fail", "Accepted ids missing after calibration.")
    if not confidence_moved:
        return EfficacyCheck("E6.calibrate.feedback-loop", "calibrate", "fail", "No confidence/feedback movement detected.")
    return EfficacyCheck(
        "E6.calibrate.feedback-loop",
        "calibrate",
        "pass",
        f"Suppressed {len(delta['suppressed_ids'])} ids; {len(delta['confidence_changes'])} confidence adjustments.",
    )


EVALUATORS = (
    evaluate_e1_detect,
    evaluate_e2_anchor,
    evaluate_e3_dogfood,
    evaluate_e4_promote,
    evaluate_e5_publish,
    evaluate_e6_calibrate,
)


def evaluate_all(repo_root: Path) -> list[EfficacyCheck]:
    return [evaluator(repo_root) for evaluator in EVALUATORS]


def render_eval_report(checks: list[EfficacyCheck]) -> str:
    passed = sum(1 for check in checks if check.status == "pass")
    failed = sum(1 for check in checks if check.status == "fail")
    lines = [
        "# Baseline Efficacy Evaluation",
        "",
        f"- Passed: `{passed}`",
        f"- Failed: `{failed}`",
        f"- Total: `{len(checks)}`",
        "",
        "| Metric | Phase | Status | Detail |",
        "|--------|-------|--------|--------|",
    ]
    for check in checks:
        lines.append(f"| `{check.metric_id}` | {check.phase} | {check.status} | {check.detail} |")
    return "\n".join(lines) + "\n"


def baseline_eval(config: ArchiveConfig, output: Path | None = None, dry_run: bool = False) -> int:
    checks = evaluate_all(config.repo_root)
    report = render_eval_report(checks)
    if dry_run:
        print(report)
        return 0 if all(check.status == "pass" for check in checks) else 1
    target = output or config.repo_root / "baseline" / "calibration" / "efficacy-report.md"
    if not target.is_absolute():
        target = config.repo_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote {target}")
    failed = [check for check in checks if check.status == "fail"]
    if failed:
        print(f"Efficacy evaluation failed ({len(failed)} metric(s)).")
        return 1
    print("All efficacy metrics passed.")
    return 0