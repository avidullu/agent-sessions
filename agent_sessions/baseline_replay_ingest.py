"""Ingest external replay results into the grounded pipeline (#25, K11).

An out-of-band replayer/judge hands back a structured result for a session it
re-executed. `baseline replay ingest` validates that result, records it in an
append-only ledger, and — when the judge recommends it — emits a `replay.*`
proposal that flows through the *existing* human-gated pipeline
(`baseline ingest` -> candidate -> calibrate -> promote). Nothing is ever
auto-promoted.

Trust boundary: results come from an external agent, so provenance is verified
before anything becomes a candidate. `replay_of` must resolve to a real
`archive/index.jsonl` session, and the generated proposal must pass the same K5
`validate_proposal` gate as any other external producer. Unresolvable results
are rejected and recorded in the ledger as such.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .baseline_ingest import load_archive_references, validate_proposal
from .baseline_settings import load_baseline_settings
from .config import ArchiveConfig
from .utils import read_jsonl_dicts, slugify

REPLAY_INGEST_PRODUCER = "baseline replay ingest"
REPLAY_RESULT_REQUIRED = ("replay_of", "replayer", "rubric_version", "claim", "confidence", "recommended_action")
VALID_ACTIONS = {"proposal", "watchlist", "reject"}
ENUM_CONFIDENCE = {"high": 0.8, "medium": 0.6, "low": 0.4}


def load_replay_results(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def session_markdown_map(records: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for record in records:
        markdown = str(record.get("markdown", "")).replace("\\", "/").strip()
        if not markdown:
            continue
        raw_meta = record.get("metadata")
        metadata = raw_meta if isinstance(raw_meta, dict) else {}
        for session_id in (
            str(metadata.get("session_id") or metadata.get("id") or "").strip(),
            str(record.get("session_id") or "").strip(),
        ):
            if session_id:
                mapping.setdefault(session_id, markdown)
    return mapping


def numeric_confidence(value: Any) -> float | None:
    if isinstance(value, str) and value.strip().lower() in ENUM_CONFIDENCE:
        return ENUM_CONFIDENCE[value.strip().lower()]
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return confidence


def validate_replay_result(data: dict[str, Any], session_ids: frozenset[str]) -> list[str]:
    errors: list[str] = []
    for field in REPLAY_RESULT_REQUIRED:
        if field not in data or data[field] in ("", None):
            errors.append(f"missing `{field}`")
    action = str(data.get("recommended_action", "")).strip().lower()
    if action and action not in VALID_ACTIONS:
        errors.append(f"invalid recommended_action `{data['recommended_action']}`")
    if "confidence" in data and numeric_confidence(data["confidence"]) is None:
        errors.append("confidence must be numeric 0-1 or one of high/medium/low")
    replay_of = str(data.get("replay_of", "")).strip()
    if replay_of and replay_of not in session_ids:
        errors.append(f"unresolved replay_of `{replay_of}` (not in archive/index.jsonl)")
    return errors


def replay_result_to_proposal(
    data: dict[str, Any], markdown_for_session: dict[str, str], project_slug: str = ""
) -> dict[str, Any]:
    replay_of = str(data["replay_of"]).strip()
    markdown = markdown_for_session.get(replay_of, "")
    claim = str(data["claim"]).strip()
    replayer = str(data.get("replayer", "")).strip()
    confidence = numeric_confidence(data.get("confidence")) or 0.5
    evidence = [str(item) for item in data.get("evidence", []) if str(item).strip()]
    # Derive scope from the replayed session's project when available;
    # fall back to global/metacognition for sessions with no project slug.
    scope = f"project:{project_slug}" if project_slug else "global"
    category = "project" if project_slug else "metacognition"
    trace = {
        "source": "replay",
        "session_id": replay_of,
        "markdown_path": markdown,
        "transform": REPLAY_INGEST_PRODUCER,
        "bundle_id": str(data.get("bundle_id", "")).strip(),
        "evidence_excerpt": claim[:200],
    }
    return {
        "id": f"replay.{slugify(replay_of)[:24]}",
        "title": f"Replay improvement for session {replay_of}",
        "scope": scope,
        "category": category,
        "risk": "low",
        "confidence": round(confidence, 2),
        "approval_mode": "strict",
        "generated_by": REPLAY_INGEST_PRODUCER,
        "source_kind": "replay",
        "replay_of": replay_of,
        "replayer": replayer,
        "rubric_version": str(data.get("rubric_version", "")).strip(),
        "evidence": [f"replay of session {replay_of} by {replayer or 'unknown replayer'}", *evidence],
        "trace": [{key: value for key, value in trace.items() if value}],
        "suggested_baseline_text": claim,
        "open_questions": ["Does the replayed improvement generalize beyond this one session?"],
    }


def stable_ledger_id(data: dict[str, Any]) -> str:
    parts = "|".join(str(data.get(field, "")) for field in ("replay_of", "replayer", "rubric_version", "claim"))
    return "replay-result." + hashlib.sha256(parts.encode("utf-8")).hexdigest()[:12]


def ledger_record(data: dict[str, Any], *, resolved: bool, proposal_id: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "id": stable_ledger_id(data),
        "replay_of": str(data.get("replay_of", "")).strip(),
        "replayer": str(data.get("replayer", "")).strip(),
        "rubric_version": str(data.get("rubric_version", "")).strip(),
        "recommended_action": str(data.get("recommended_action", "")).strip().lower(),
        "confidence": data.get("confidence"),
        "resolved": resolved,
        "proposal_id": proposal_id,
        "reasons": reasons,
    }


def merge_ledger(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {str(record.get("id")): record for record in existing if record.get("id")}
    for record in new:
        merged[str(record["id"])] = record
    return sorted(merged.values(), key=lambda record: str(record.get("id")))


def render_ledger_jsonl(records: list[dict[str, Any]]) -> str:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    return "\n".join(lines) + ("\n" if lines else "")


def assert_generated_proposal_target(path: Path) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Refusing to overwrite non-JSON proposal: {path}") from exc
    if not isinstance(data, dict) or data.get("generated_by") != REPLAY_INGEST_PRODUCER:
        raise SystemExit(f"Refusing to overwrite non-generated proposal: {path}")


def baseline_replay_ingest(
    config: ArchiveConfig,
    *,
    result: Path | None = None,
    output_dir: Path | None = None,
    ledger: Path | None = None,
    dry_run: bool = False,
) -> int:
    if result is None:
        raise SystemExit("--result is required (path to a replay result JSON).")
    result_path = result if result.is_absolute() else config.repo_root / result
    if not result_path.exists():
        raise SystemExit(f"Replay result does not exist: {result_path}.")

    settings = load_baseline_settings(config)
    refs = load_archive_references(config)
    session_ids = refs.session_ids if refs else frozenset()
    index_path = config.archive_dir / "index.jsonl"
    records = read_jsonl_dicts(index_path, label="archive/index.jsonl") if index_path.exists() else []
    markdown_for_session = session_markdown_map(records)

    # Build session_id → project_slug lookup from archive metadata so
    # replay proposals carry the correct project scope.
    session_project: dict[str, str] = {}
    for record in records:
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        sid = str(metadata.get("session_id") or metadata.get("id") or "").strip()
        if sid:
            raw = str(metadata.get("project") or metadata.get("cwd") or "").strip()
            if raw:
                from .baseline_replay import project_slug_from_metadata

                session_project[sid] = project_slug_from_metadata(metadata, settings)

    proposals_dir = output_dir or settings.root / "proposals"
    if not proposals_dir.is_absolute():
        proposals_dir = config.repo_root / proposals_dir
    ledger_path = ledger or settings.root / "replay" / "ledger.jsonl"
    if not ledger_path.is_absolute():
        ledger_path = config.repo_root / ledger_path

    results = load_replay_results(result_path)
    proposals: list[dict[str, Any]] = []
    ledger_new: list[dict[str, Any]] = []
    accepted = 0
    rejected = 0
    for data in results:
        errors = validate_replay_result(data, session_ids)
        action = str(data.get("recommended_action", "")).strip().lower()
        if errors:
            rejected += 1
            ledger_new.append(ledger_record(data, resolved=False, proposal_id="", reasons=errors))
            continue
        proposal_id = ""
        if action == "proposal":
            project_slug = session_project.get(str(data.get("replay_of", "")).strip(), "")
            proposal = replay_result_to_proposal(data, markdown_for_session, project_slug)
            proposal_errors = validate_proposal(proposal, refs)
            if proposal_errors:
                rejected += 1
                ledger_new.append(ledger_record(data, resolved=False, proposal_id="", reasons=proposal_errors))
                continue
            proposals.append(proposal)
            proposal_id = str(proposal["id"])
        accepted += 1
        ledger_new.append(ledger_record(data, resolved=True, proposal_id=proposal_id, reasons=[]))

    ledger_all = merge_ledger(
        read_jsonl_dicts(ledger_path, label=str(ledger_path)) if ledger_path.exists() else [],
        ledger_new,
    )
    summary = (
        f"Replay ingest: {len(results)} result(s) -> {accepted} accepted, {rejected} rejected, "
        f"{len(proposals)} `replay.*` proposal(s)."
    )
    if dry_run:
        for proposal in proposals:
            print(json.dumps(proposal, indent=2, ensure_ascii=False, sort_keys=True))
        print(summary)
        return 1 if rejected else 0

    for proposal in proposals:
        target = proposals_dir / f"{proposal['id']}.json"
        assert_generated_proposal_target(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(proposal, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"Wrote {target}")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(render_ledger_jsonl(ledger_all), encoding="utf-8", newline="\n")
    print(f"Wrote {ledger_path}")
    print(summary)
    return 1 if rejected else 0
