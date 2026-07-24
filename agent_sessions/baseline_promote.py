"""Marker-block parsing/rendering and promotion of accepted guardrails."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from .baseline_settings import (
    PROJECT_README_PLACEHOLDER,
    load_baseline_settings,
    load_feedback,
    resolve_prediction_sidecar,
)
from .baseline_types import BaselineSettings, parse_verdict
from .config import ArchiveConfig

PROMOTION_BEGIN = '<!-- baseline:begin id="{id}" -->'
PROMOTION_END = '<!-- baseline:end id="{id}" -->'
PROMOTED_PLACEHOLDER = "Promoted guidance will land here."
PROJECT_PAGE_TRACE_FIELDS = (
    "source",
    "source_file",
    "markdown_path",
    "session_id",
    "timestamp",
    "project_slug",
    "repo",
    "evidence_anchor",
    "evidence_excerpt",
    "transform",
    "bundle_id",
    "calibration_effect",
)
BASELINE_BLOCK_RE = re.compile(
    r'<!-- baseline:begin id="([^"]+)" -->\n?(.*?)<!-- baseline:end id="\1" -->',
    re.DOTALL,
)


def category_promotion_target(category: str) -> str:
    if category == "regression-frameworks":
        return "regression-frameworks.md"
    return "engineering-guardrails.md"


def parse_promoted_blocks(content: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for match in BASELINE_BLOCK_RE.finditer(content):
        blocks[match.group(1)] = match.group(0).strip()
    return blocks


def render_promoted_block(
    prediction: dict[str, Any],
    run_id: str,
    feedback_note: str,
    promoted_at: str,
) -> str:
    prediction_id = str(prediction.get("id", ""))
    title = str(prediction.get("title", prediction_id))
    confidence = float(prediction.get("confidence", 0))
    text = str(prediction.get("text", "")).strip()
    evidence = prediction.get("evidence", [])
    lines = [
        PROMOTION_BEGIN.format(id=prediction_id),
        f"## {title}",
        "",
        f"**ID:** `{prediction_id}`",
        f"**Promoted:** {promoted_at}",
        f"**Run:** {run_id}",
        f"**Confidence:** {confidence:.2f}",
    ]
    if feedback_note:
        lines.append(f"**Review note:** {feedback_note}")
    lines.extend(["", text, "", "### Evidence"])
    if isinstance(evidence, list) and evidence:
        for item in evidence:
            lines.append(f"- {item}")
    else:
        lines.append("- No evidence recorded in prediction sidecar.")
    lines.append(PROMOTION_END.format(id=prediction_id))
    return "\n".join(lines)


def global_baseline_header(filename: str) -> str:
    titles = {
        "engineering-guardrails.md": "Engineering Guardrails",
        "regression-frameworks.md": "Regression Frameworks",
    }
    title = titles.get(filename, filename.replace(".md", "").replace("-", " ").title())
    return (
        f"# {title}\n\n"
        "Promoted guidance derived from reviewed baseline candidates.\n"
    )


def project_page_header(slug: str) -> str:
    return f"# {slug}\n"


def project_page_placeholder(slug: str) -> str:
    return PROJECT_README_PLACEHOLDER.format(slug=slug)


def _drop_placeholder_lines(content: str, placeholders: Sequence[str]) -> str:
    placeholder_set = {placeholder.strip() for placeholder in placeholders if placeholder.strip()}
    result = "\n".join(line for line in content.splitlines() if line.strip() not in placeholder_set)
    return result.rstrip("\n") + "\n"


def _upsert_marker_blocks(
    existing: str,
    blocks: dict[str, str],
    *,
    empty_header: str,
    placeholders: Sequence[str] = (),
) -> str:
    if not blocks:
        return existing
    # Fresh/empty file: lay down the caller's header plus the new blocks.
    result = empty_header.rstrip("\n") + "\n" if not existing.strip() else existing
    if existing.strip():
        result = _drop_placeholder_lines(result, placeholders)
    appended: list[str] = []
    for block_id in sorted(blocks):
        block = blocks[block_id]
        marker = re.compile(
            r'<!-- baseline:begin id="' + re.escape(block_id) + r'" -->\n?.*?'
            r'<!-- baseline:end id="' + re.escape(block_id) + r'" -->',
            re.DOTALL,
        )
        if marker.search(result):
            # The replacement is a function, not a string, so `block` is
            # substituted literally — backslashes and \1-style group references
            # inside a promoted block must not be reinterpreted by re.
            #
            # B023: bind `block` as a default argument rather than closing over
            # the loop variable. This is behaviour-preserving (re.sub calls the
            # replacement eagerly, within this iteration, so the closure could
            # never have observed a later value) and removes the late-binding
            # hazard if this ever becomes lazy.
            def _replace(_match: re.Match[str], _block: str = block) -> str:
                return _block

            result = marker.sub(_replace, result, count=1)
        else:
            appended.append(block)
    if appended:
        result = result.rstrip("\n") + "\n\n" + "\n\n".join(appended) + "\n"
    return result


def upsert_promoted_content(existing: str, blocks: dict[str, str], filename: str) -> str:
    return _upsert_marker_blocks(
        existing,
        blocks,
        empty_header=global_baseline_header(filename),
        placeholders=(PROMOTED_PLACEHOLDER,),
    )


def render_project_page_block(
    block_id: str,
    title: str,
    body: str,
    *,
    generated_by: str,
    generated_at: str,
    traces: Sequence[Mapping[str, str]] = (),
) -> str:
    lines = [
        PROMOTION_BEGIN.format(id=block_id),
        f"## {title}",
        "",
        f"**Generated by:** `{generated_by}`",
        f"**Generated at:** {generated_at}",
        "",
        body.strip() or "_No generated content._",
    ]
    if traces:
        lines.extend(["", "### Trace"])
        for trace in traces:
            fields: list[str] = []
            seen: set[str] = set()
            for key in PROJECT_PAGE_TRACE_FIELDS:
                value = trace.get(key, "").strip()
                if value:
                    fields.append(f"`{key}`={value}")
                    seen.add(key)
            for key in sorted(set(trace) - seen):
                value = trace.get(key, "").strip()
                if value:
                    fields.append(f"`{key}`={value}")
            if fields:
                lines.append("- " + "; ".join(fields))
    lines.append(PROMOTION_END.format(id=block_id))
    return "\n".join(lines)


def upsert_project_page_content(existing: str, blocks: dict[str, str], slug: str) -> str:
    return _upsert_marker_blocks(
        existing,
        blocks,
        empty_header=project_page_header(slug),
        placeholders=(project_page_placeholder(slug),),
    )


def select_promotable_predictions(
    predictions: list[dict[str, Any]],
    feedback_map: dict[str, dict[str, str]],
    ids: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for prediction in predictions:
        prediction_id = str(prediction.get("id", ""))
        if ids and prediction_id not in ids:
            continue
        if not prediction_id.startswith("guardrail."):
            continue
        feedback = feedback_map.get(prediction_id)
        if not feedback:
            continue
        if parse_verdict(feedback) != "accept":
            continue
        selected.append(prediction)
    return selected


def promote_predictions(
    settings: BaselineSettings,
    predictions: list[dict[str, Any]],
    feedback_map: dict[str, dict[str, str]],
    run_id: str,
    promoted_at: str,
    ids: tuple[str, ...] | None = None,
) -> dict[Path, str]:
    promotable = select_promotable_predictions(predictions, feedback_map, ids=ids)
    grouped: dict[str, dict[str, str]] = {}
    for prediction in promotable:
        prediction_id = str(prediction.get("id", ""))
        feedback_note = str(feedback_map.get(prediction_id, {}).get("note", "")).strip()
        target_name = category_promotion_target(str(prediction.get("category", "")))
        grouped.setdefault(target_name, {})[prediction_id] = render_promoted_block(
            prediction,
            run_id=run_id,
            feedback_note=feedback_note,
            promoted_at=promoted_at,
        )
    updates: dict[Path, str] = {}
    for target_name, blocks in grouped.items():
        path = settings.root / "global" / target_name
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        updates[path] = upsert_promoted_content(existing, blocks, target_name)
    return updates


def baseline_promote(
    config: ArchiveConfig,
    feedback: Path,
    predictions: Path | None = None,
    dry_run: bool = False,
    ids: tuple[str, ...] | None = None,
) -> int:
    settings = load_baseline_settings(config)
    feedback_map = load_feedback(config, feedback)
    prediction_path = resolve_prediction_sidecar(settings, predictions)
    prediction_data = json.loads(prediction_path.read_text(encoding="utf-8"))
    run_id = str(prediction_data.get("run_id", prediction_path.stem.replace(".predictions", "")))
    promoted_at = dt.date.today().isoformat()
    updates = promote_predictions(
        settings=settings,
        predictions=cast(list[dict[str, Any]], prediction_data.get("predictions", [])),
        feedback_map=feedback_map,
        run_id=run_id,
        promoted_at=promoted_at,
        ids=ids,
    )
    if not updates:
        print("No accepted guardrail predictions to promote.")
        return 0
    for path, content in updates.items():
        if dry_run:
            print(f"Would write {path}")
            print(content)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote {path}")
    return 0
