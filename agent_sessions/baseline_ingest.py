"""Ingest structured baseline proposals from baseline/proposals/."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .baseline import BaselineSettings, Prediction, load_baseline_settings, prediction_to_dict
from .config import ArchiveConfig


REQUIRED_FIELDS = (
    "id",
    "title",
    "scope",
    "category",
    "risk",
    "confidence",
    "evidence",
    "suggested_baseline_text",
)
VALID_RISKS = {"low", "medium", "high"}
SKIP_FILENAMES = {"proposal.schema.json", "README.md"}


def validate_proposal(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data or data[field] in ("", None):
            errors.append(f"missing `{field}`")
    if "confidence" in data:
        try:
            confidence = float(data["confidence"])
            if not 0.0 <= confidence <= 1.0:
                errors.append("confidence must be between 0 and 1")
        except (TypeError, ValueError):
            errors.append("confidence must be numeric")
    if "risk" in data and str(data["risk"]).lower() not in VALID_RISKS:
        errors.append(f"invalid risk `{data['risk']}`")
    evidence = data.get("evidence")
    if evidence is not None and not isinstance(evidence, list):
        errors.append("evidence must be a list")
    return errors


def proposal_to_prediction(data: dict[str, Any]) -> Prediction:
    return Prediction(
        id=str(data["id"]),
        title=str(data["title"]),
        scope=str(data["scope"]),
        risk=str(data["risk"]).lower(),
        category=str(data["category"]),
        confidence=float(data["confidence"]),
        status="proposed",
        evidence=[str(item) for item in data.get("evidence", [])],
        text=str(data["suggested_baseline_text"]),
        feedback="ingested",
    )


def discover_proposal_paths(proposals_dir: Path, proposal: Path | None = None) -> list[Path]:
    if proposal is not None:
        return [proposal]
    return sorted(
        path
        for path in proposals_dir.glob("*.json")
        if path.name not in SKIP_FILENAMES
    )


def load_proposals(paths: list[Path]) -> tuple[list[Prediction], list[tuple[Path, list[str]]]]:
    accepted: list[Prediction] = []
    rejected: list[tuple[Path, list[str]]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rejected.append((path, [f"invalid json: {exc.msg}"]))
            continue
        if not isinstance(data, dict):
            rejected.append((path, ["proposal must be a JSON object"]))
            continue
        errors = validate_proposal(data)
        if errors:
            rejected.append((path, errors))
            continue
        accepted.append(proposal_to_prediction(data))
    return accepted, rejected


def render_ingest_report(
    accepted: list[Prediction],
    rejected: list[tuple[Path, list[str]]],
    source_paths: list[Path],
) -> str:
    lines = [
        f"# Baseline Proposal Ingest ({dt.date.today().isoformat()})",
        "",
        f"- Proposals scanned: `{len(source_paths)}`",
        f"- Accepted: `{len(accepted)}`",
        f"- Rejected: `{len(rejected)}`",
        "",
    ]
    if accepted:
        lines.extend(["## Accepted Proposals", ""])
        for prediction in accepted:
            lines.append(f"- `{prediction.id}` — {prediction.title} (confidence {prediction.confidence:.2f})")
        lines.append("")
    if rejected:
        lines.extend(["## Rejected Proposals", ""])
        for path, errors in rejected:
            lines.append(f"- `{path.name}`: {', '.join(errors)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_ingest_artifacts(
    settings: BaselineSettings,
    accepted: list[Prediction],
    report: str,
    report_path: Path,
) -> tuple[Path, Path]:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path = report_path.with_suffix(".predictions.json")
    run_id = report_path.stem
    payload = {
        "run_id": run_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "baseline ingest",
        "candidate": str(report_path.relative_to(settings.root.parent)).replace("\\", "/"),
        "predictions": [prediction_to_dict(prediction) for prediction in accepted],
    }
    report_path.write_text(report, encoding="utf-8", newline="\n")
    sidecar_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return report_path, sidecar_path


def baseline_ingest(
    config: ArchiveConfig,
    proposal: Path | None = None,
    output: Path | None = None,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    proposals_dir = settings.root / "proposals"
    if proposal is not None and not proposal.is_absolute():
        proposal = config.repo_root / proposal
    paths = discover_proposal_paths(proposals_dir, proposal=proposal)
    if not paths:
        print(f"No proposal JSON files found in {proposals_dir}.")
        return 0

    accepted, rejected = load_proposals(paths)
    report = render_ingest_report(accepted, rejected, paths)
    run_id = output.stem if output else f"{dt.date.today().isoformat()}-ingested"
    if output is not None and not output.is_absolute():
        output = config.repo_root / output

    if dry_run:
        print(report)
        print(f"Would ingest {len(accepted)} proposal(s); rejected {len(rejected)}.")
        return 0

    if output is not None:
        report_path, sidecar_path = write_ingest_artifacts(settings, accepted, report, output)
    else:
        report_path = settings.candidates_dir / f"{run_id}.md"
        report_path, sidecar_path = write_ingest_artifacts(settings, accepted, report, report_path)
    print(f"Wrote {report_path}")
    print(f"Wrote {sidecar_path}")

    if rejected:
        print(f"Skipped {len(rejected)} invalid proposal file(s).")
    return 0