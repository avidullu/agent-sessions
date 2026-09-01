"""Transferable concepts, not personal policy or memorized project facts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .baseline_redaction import redact_text
from .copilot_records import digest, timestamp

CONCEPTS = {
    "state_reconciliation": "Check observed current state before repeating a side effect; distinguish stale and current evidence.",
    "evidence_calibration": "Distinguish proposals, claims, observations and verified outcomes; expose uncertainty.",
    "causal_diagnosis": "Use discriminating observations to locate a failure; do not confuse correlation with cause.",
    "constraint_revision": "Incorporate corrections and current user constraints without retaining superseded assumptions.",
    "outcome_learning": "Prefer practices supported by outcomes; test transfer before treating a lesson as general.",
}


def validate_entity_mapping(value: Any) -> dict[str, str]:
    """Validate the reviewer-owned substitutions used by every dataset path."""
    if not isinstance(value, dict) or any(
        not isinstance(k, str)
        or len(k) < 3
        or not isinstance(v, str)
        or not re.fullmatch(r"ENTITY_[A-Z]+_[0-9]+", v)
        for k, v in value.items()
    ):
        raise ValueError("entity mapping requires source strings and ENTITY_TYPE_N placeholders")
    if len(set(value.values())) != len(value):
        raise ValueError("distinct source entities must keep distinct placeholders")
    return value


def abstract_case(candidate: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Apply reviewer-specified, consistent entity substitutions to the whole case.

    The mapping stays private in the review file. Concept labels alone never
    establish that the answer is correct; source-linked review remains required.
    """
    concept = review.get("concept")
    if concept not in CONCEPTS:
        raise ValueError("review must identify a supported transferable concept")
    if review.get("concept_reviewed") is not True:
        raise ValueError("review must check that the lesson is evidence-backed, not a personal preference")
    substitutions = validate_entity_mapping(review.get("entities", {}))

    def replace(text: str) -> str:
        for old in sorted(substitutions, key=len, reverse=True):
            text = text.replace(old, substitutions[old])
        return text

    case = dict(candidate)
    case["question"] = replace(review.get("question", candidate["question"]))
    case["answer"] = replace(review["answer"])
    case["evidence"] = [{**e, "text": replace(e["text"])} for e in candidate["evidence"]]
    case["concept"] = concept
    # Stable case-local citations prevent learning user/session identifiers.
    refs = {e["event_id"]: f"E{i + 1}" for i, e in enumerate(case["evidence"])}
    for original, local in refs.items():
        case["answer"] = case["answer"].replace(f"[{original}]", f"[{local}]")
    case["evidence"] = [
        {"event_id": refs[e["event_id"]], "role": e["role"], "timestamp": e["timestamp"], "text": e["text"]}
        for e in case["evidence"]
    ]
    return case


def propose_lesson(corpus: Path, proposal: dict[str, Any], output: Path) -> dict[str, Any]:
    """Append a correction or lesson beside immutable logs; never silently fix history."""
    from .copilot_dataset import private_dir, read_jsonl, write_jsonl

    if proposal.get("kind") not in ("correction", "lesson", "withdrawal"):
        raise ValueError("proposal kind must be correction, lesson, or withdrawal")
    if proposal.get("concept") not in CONCEPTS or not timestamp(proposal.get("created_at")):
        raise ValueError("concept and explicit timezone-aware creation time required")
    records = read_jsonl(corpus / "sessions.jsonl")
    events = {e["event_id"]: e for r in records for e in r["messages"]}
    refs = proposal.get("evidence_ids", [])
    if not refs or any(ref not in events for ref in refs):
        raise ValueError("proposal requires evidence from this workspace snapshot")
    if any(events[ref]["timestamp"] > timestamp(proposal["created_at"]) for ref in refs):
        raise ValueError("proposal cites future evidence")
    statement = proposal.get("statement", "")
    clean = redact_text(statement)
    if not statement.strip() or clean.blocked:
        raise ValueError("unsafe or empty proposal")
    result = {
        "schema": "session-copilot-lesson.v1",
        "kind": proposal["kind"],
        "concept": proposal["concept"],
        "statement": clean.redacted_text,
        "evidence_ids": refs,
        "created_at": timestamp(proposal["created_at"]),
        "status": "proposed",
        "supersedes": proposal.get("supersedes"),
        "corpus_sha256": digest(records),
        "model_training_authorized": False,
    }
    result["id"] = digest(result)
    output = private_dir(output)
    write_jsonl(output / f"{result['id']}.jsonl", [result])
    return result


def transfer_case(case: dict[str, Any], replacements: dict[str, str]) -> dict[str, Any]:
    """Metamorphic renaming, with the reference renamed too; not a teacher-generated answer.

    Fact-changing counterexamples must be separately reviewed. Renaming alone
    tests identity invariance, not reasoning or transfer to an actual new user.
    """
    clone = json.loads(json.dumps(case))
    for old, new in replacements.items():
        if not old or old == new:
            raise ValueError("transfer substitution must change a named entity")
        for message in clone["messages"]:
            message["content"] = message["content"].replace(old, new)
    clone["id"] = digest([case["id"], replacements])
    clone["variant_of"] = case["id"]
    clone["variant_kind"] = "entity_rename"
    return clone
