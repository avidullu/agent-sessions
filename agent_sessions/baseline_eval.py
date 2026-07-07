"""Programmatic efficacy gate evaluation for the baseline loop."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .baseline import apply_feedback
from .baseline_calibration import apply_calibration_loop, calibration_delta, load_ledger_entries
from .baseline_predictions import build_predictions
from .baseline_promote import PROMOTED_PLACEHOLDER, parse_promoted_blocks
from .baseline_settings import load_baseline_settings, load_feedback
from .baseline_types import parse_verdict
from .config import ArchiveConfig, read_toml
from .utils import read_jsonl_dicts

# Thresholds for E5 (published agent slice must carry real promoted content).
MIN_PUBLISHED_LINES = 20
MIN_PUBLISHED_RULES = 3
# Minimum distinct P-numbered tracker rows E3 expects in a tracked project doc.
MIN_TRACKER_ROWS = 2


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


def evaluate_e1_detect(config: ArchiveConfig) -> EfficacyCheck:
    repo_root = config.repo_root
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


def evaluate_e2_anchor(config: ArchiveConfig) -> EfficacyCheck:
    config_path = config.repo_root / "config" / "baseline.toml"
    data = read_toml(config_path) if config_path.exists() else {}
    anchors = data.get("calibration_anchors", [])
    # Config-driven: any tracked-project-doc anchor satisfies the gate; the
    # specific source repo lives in config/baseline.toml, not hardcoded here.
    template_anchor = next(
        (anchor for anchor in anchors if anchor.get("kind") == "tracked-project-doc"),
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


def evaluate_e3_dogfood(config: ArchiveConfig) -> EfficacyCheck:
    doc = config.repo_root / "docs" / "BASELINE_LOOP_CLOSURE.md"
    text = _read_text(doc)
    if not text or "§7" not in text and "progress tracker" not in text.lower():
        return EfficacyCheck("E3.dogfood.tracked-project-doc", "dogfood", "fail", "BASELINE_LOOP_CLOSURE tracker missing.")
    # Generic: a tracked project doc has P-numbered deliverable rows; count
    # distinct P-numbers instead of pinning to specific ids like P0/P9.
    tracker_rows = {match for match in re.findall(r"\bP\d+\b", text)}
    if len(tracker_rows) < MIN_TRACKER_ROWS:
        return EfficacyCheck(
            "E3.dogfood.tracked-project-doc",
            "dogfood",
            "fail",
            f"Fewer than {MIN_TRACKER_ROWS} P-numbered tracker rows found.",
        )
    return EfficacyCheck(
        "E3.dogfood.tracked-project-doc",
        "dogfood",
        "pass",
        f"Tracked project doc with §7 rows present ({len(tracker_rows)} P-rows).",
    )


def evaluate_e4_promote(config: ArchiveConfig) -> EfficacyCheck:
    path = config.repo_root / "baseline" / "global" / "engineering-guardrails.md"
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


def count_published_rules(text: str) -> int:
    ids = re.findall(r'\*\*ID:\*\* `((?:guardrail\.|profile\.)[^`]+)`', text)
    return len(set(ids))


def evaluate_e5_publish(config: ArchiveConfig) -> EfficacyCheck:
    path = config.repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md"
    if not path.exists():
        return EfficacyCheck("E5.publish.agent-slices", "publish", "fail", "CLAUDE.generated.md missing.")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rule_count = count_published_rules(text)
    if len(lines) <= MIN_PUBLISHED_LINES or rule_count < MIN_PUBLISHED_RULES:
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


def evaluate_e6_calibrate(config: ArchiveConfig) -> EfficacyCheck:
    feedback_path = config.repo_root / "baseline" / "calibration" / "feedback.example.toml"
    if not feedback_path.exists():
        return EfficacyCheck("E6.calibrate.feedback-loop", "calibrate", "fail", "feedback.example.toml missing.")

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
        prediction_id for prediction_id, item in feedback_map.items() if parse_verdict(item) == "reject"
    ]
    suppressed_rejected = all(prediction_id in delta["suppressed_ids"] for prediction_id in rejected_ids)
    accepted_ids = [
        prediction_id for prediction_id, item in feedback_map.items() if parse_verdict(item) == "accept"
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


def evaluate_extended_gates(config: ArchiveConfig) -> list[EfficacyCheck]:
    """K12: wiki-lint (W), handoff (H), replay (R) and governance gates.

    Uses a third status, ``gated``, for gates whose prerequisites don't exist yet
    (e.g. no external replay result has been ingested), so they are reported
    honestly rather than counted as failures or falsely passed."""
    from .baseline_lint import lint_baseline
    from .baseline_redaction import SCANNER_VERSION

    repo = config.repo_root
    checks: list[EfficacyCheck] = []

    findings = lint_baseline(config)
    schema_errors = [f for f in findings if f.severity == "error" and f.rule_id in ("W1-schema", "W1-marker")]
    link_errors = [f for f in findings if f.severity == "error" and f.rule_id == "W2-links"]
    checks.append(
        EfficacyCheck(
            "W1-schema",
            "wiki-lint",
            "pass" if not schema_errors else "fail",
            "No schema/marker errors." if not schema_errors else f"{len(schema_errors)} schema/marker error(s).",
        )
    )
    checks.append(
        EfficacyCheck(
            "W2-links",
            "wiki-lint",
            "pass" if not link_errors else "fail",
            "No broken generated links." if not link_errors else f"{len(link_errors)} broken generated link(s).",
        )
    )

    handoff_index = read_jsonl_dicts(repo / "baseline" / "handoffs" / "index.jsonl", label="handoff-index") if (
        repo / "baseline" / "handoffs" / "index.jsonl"
    ).exists() else []
    checks.append(
        EfficacyCheck(
            "H1-handoff-precision",
            "handoff",
            "pass" if handoff_index else "gated",
            f"{len(handoff_index)} handoff record(s) indexed." if handoff_index else "No handoff index yet.",
        )
    )
    audit = repo / "baseline" / "handoffs" / "audit.md"
    audit_ok = audit.exists() and "Stale threshold" in _read_text(audit)
    checks.append(
        EfficacyCheck(
            "H2-handoff-freshness",
            "handoff",
            "pass" if audit_ok else "gated",
            "Handoff audit reports freshness." if audit_ok else "No handoff audit yet.",
        )
    )

    manifest = repo / "baseline" / "replay" / "manifest.jsonl"
    manifest_records = read_jsonl_dicts(manifest, label="replay-manifest") if manifest.exists() else []
    selected = [r for r in manifest_records if r.get("selected") is True]
    checks.append(
        EfficacyCheck(
            "R1-select",
            "replay",
            "pass" if selected else "gated",
            f"{len(selected)} selected replay candidate(s)." if selected else "No replay manifest yet.",
        )
    )
    ids = [r.get("id") for r in manifest_records]
    if not manifest_records:
        checks.append(EfficacyCheck("R2-dedup", "replay", "gated", "No manifest to check for dedup."))
    elif len(ids) == len(set(ids)):
        checks.append(EfficacyCheck("R2-dedup", "replay", "pass", "Manifest ids unique (deterministic dedup holds)."))
    else:
        checks.append(EfficacyCheck("R2-dedup", "replay", "fail", "Duplicate ids in replay manifest."))

    ledger = repo / "baseline" / "replay" / "ledger.jsonl"
    ledger_records = read_jsonl_dicts(ledger, label="replay-ledger") if ledger.exists() else []
    has_proposal = any(r.get("proposal_id") for r in ledger_records)
    checks.append(
        EfficacyCheck(
            "R3-signal",
            "replay",
            "pass" if has_proposal else "gated",
            "At least one replay-derived proposal recorded."
            if has_proposal
            else "No replay-derived proposal yet (needs an external replay result).",
        )
    )
    checks.append(
        EfficacyCheck(
            "R4-value",
            "replay",
            "gated",
            "Replay acceptance not yet measurable against non-replay candidates.",
        )
    )
    gitignore = _read_text(repo / ".gitignore")
    r5_ok = "baseline/replay/bundles/" in gitignore and bool(SCANNER_VERSION)
    checks.append(
        EfficacyCheck(
            "R5-safety",
            "replay",
            "pass" if r5_ok else "fail",
            f"Bundles gitignored; redaction scanner `{SCANNER_VERSION}`."
            if r5_ok
            else "Bundle gitignore or redaction scanner missing.",
        )
    )

    auto_promote = _proposals_requesting_auto_promote(repo / "baseline" / "proposals")
    checks.append(
        EfficacyCheck(
            "G-no-autopromote",
            "governance",
            "pass" if not auto_promote else "fail",
            "No proposal requests auto-promote." if not auto_promote else f"Auto-promote requested by: {auto_promote}.",
        )
    )
    return checks


def _proposals_requesting_auto_promote(proposals_dir: Path) -> list[str]:
    offenders: list[str] = []
    if not proposals_dir.exists():
        return offenders
    for path in sorted(proposals_dir.glob("*.json")):
        if path.name == "proposal.schema.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and str(data.get("approval_mode", "")).lower() == "auto-promote":
            offenders.append(path.name)
    return offenders


def evaluate_all(config: ArchiveConfig) -> list[EfficacyCheck]:
    checks = [evaluator(config) for evaluator in EVALUATORS]
    checks.extend(evaluate_extended_gates(config))
    return checks


def render_eval_report(checks: list[EfficacyCheck]) -> str:
    passed = sum(1 for check in checks if check.status == "pass")
    failed = sum(1 for check in checks if check.status == "fail")
    gated = sum(1 for check in checks if check.status == "gated")
    lines = [
        "# Baseline Efficacy Evaluation",
        "",
        f"- Passed: `{passed}`",
        f"- Failed: `{failed}`",
        f"- Gated (prerequisite pending): `{gated}`",
        f"- Total: `{len(checks)}`",
        "",
        "| Metric | Phase | Status | Detail |",
        "|--------|-------|--------|--------|",
    ]
    for check in checks:
        lines.append(f"| `{check.metric_id}` | {check.phase} | {check.status} | {check.detail} |")
    return "\n".join(lines) + "\n"


def baseline_eval(config: ArchiveConfig, output: Path | None = None, dry_run: bool = False) -> int:
    checks = evaluate_all(config)
    report = render_eval_report(checks)
    if dry_run:
        print(report)
        return 0 if not any(check.status == "fail" for check in checks) else 1
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