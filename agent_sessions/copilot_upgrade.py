"""User-controlled improvement cycles from saved, evidence-bound interactions."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .baseline_redaction import redact_text
from .copilot_concepts import CONCEPTS
from .copilot_dataset import private_dir, read_jsonl, write_jsonl
from .copilot_records import digest


def _one(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("feedback inputs must be regular, non-symlink files")
    rows = read_jsonl(path)
    if len(rows) != 1:
        raise ValueError("file must contain exactly one record")
    return rows[0]


def record_feedback(
    interaction_path: Path,
    *,
    verdict: str,
    reviewer: str,
    concept: str,
    grounded: bool,
    aligned: bool,
    correction: str | None,
    allow_training_use: bool,
    output: Path,
) -> dict[str, Any]:
    interaction = _one(interaction_path)
    if interaction.get("schema") != "session-copilot-interaction.v1":
        raise ValueError("unsupported interaction record")
    if verdict not in {"accept", "correct", "reject"} or concept not in CONCEPTS or not reviewer.strip():
        raise ValueError("feedback requires a valid verdict, concept, and reviewer")
    evidence_ids = {e.get("event_id") for e in interaction.get("evidence", [])}
    if verdict == "correct" and not correction:
        raise ValueError("verdict=correct requires corrected answer text")
    if verdict != "correct" and correction:
        raise ValueError("corrected answer is only valid with verdict=correct")
    target = correction if verdict == "correct" else interaction.get("answer", "")
    if not isinstance(target, str):
        raise ValueError("feedback target must be text")
    scanned = redact_text(target)
    citations = re.findall(r"\[(E\d+)\]", target)
    trainable = verdict in {"accept", "correct"} and grounded and aligned and allow_training_use
    if trainable and (scanned.blocked or not citations or any(c not in evidence_ids for c in citations)):
        raise ValueError("training-permitted feedback requires a safe answer with valid evidence citations")
    result = {
        "schema": "session-copilot-user-feedback.v1",
        "interaction_id": interaction["id"],
        "interaction_sha256": digest(interaction),
        "verdict": verdict,
        "reviewer": reviewer.strip(),
        "concept": concept,
        "grounded": grounded,
        "aligned": aligned,
        "target_answer": scanned.redacted_text if not scanned.blocked else "",
        "training_permitted": trainable,
        "source_use_authorized": allow_training_use,
        "model_training_authorized": False,
        "interaction": interaction,
    }
    result["id"] = digest({k: v for k, v in result.items() if k != "interaction"})
    output = private_dir(output)
    write_jsonl(output / f"{result['id']}.jsonl", [result])
    return {k: v for k, v in result.items() if k != "interaction"}


def compile_cycle(
    feedback_dir: Path,
    output: Path,
    base_corpus: Path | None = None,
    base_reviews: Path | None = None,
) -> dict[str, Any]:
    if (base_corpus is None) != (base_reviews is None):
        raise ValueError("base corpus and base reviews must be supplied together")
    feedback = [_one(path) for path in sorted(feedback_dir.glob("*.jsonl"))]
    if not feedback:
        raise ValueError("no feedback records found")
    seen: set[str] = set()
    candidates = read_jsonl(base_corpus / "candidates.jsonl") if base_corpus else []
    reviews = read_jsonl(base_reviews) if base_reviews else []
    replay_examples = len(candidates)
    existing_ids = {candidate["id"] for candidate in candidates}
    counts: Counter[str] = Counter()
    for item in feedback:
        if item.get("schema") != "session-copilot-user-feedback.v1":
            raise ValueError("feedback directory contains an unsupported record")
        interaction = item.get("interaction", {})
        if item.get("interaction_sha256") != digest(interaction):
            raise ValueError("feedback interaction identity mismatch")
        key = interaction.get("id")
        if key in seen:
            raise ValueError("one interaction may have only one feedback decision per cycle")
        seen.add(key)
        counts[item["verdict"]] += 1
        if not item.get("training_permitted"):
            continue
        candidate = {
            "schema": "session-copilot-candidate.v1",
            "id": digest(["user-feedback-candidate-v1", item["id"]]),
            "family_id": interaction["family_id"],
            "project": interaction["project"],
            "category": "correction" if item["verdict"] == "correct" else "continuation",
            "as_of": interaction["as_of"],
            "question": interaction["question"],
            "evidence": interaction["evidence"],
            "draft_answer": interaction["answer"],
            "target_event_id": "",
            "review_status": "user_reviewed",
            "source_sha256": item["interaction_sha256"],
        }
        if candidate["id"] in existing_ids:
            raise ValueError("feedback candidate duplicates the replay corpus")
        existing_ids.add(candidate["id"])
        review = {
            "candidate_id": candidate["id"],
            "candidate_sha256": digest(candidate),
            "decision": "accept",
            "reviewer": item["reviewer"],
            "training_permitted": True,
            "concept": item["concept"],
            "concept_reviewed": True,
            "category": candidate["category"],
            "question": candidate["question"],
            "answer": item["target_answer"],
            "entities": (
                {interaction["project"]: "ENTITY_PROJECT_1"}
                if isinstance(interaction.get("project"), str) and len(interaction["project"]) >= 3
                else {}
            ),
            "feedback_id": item["id"],
        }
        candidates.append(candidate)
        reviews.append(review)
    output = private_dir(output)
    write_jsonl(output / "candidates.jsonl", candidates)
    write_jsonl(output / "reviews.jsonl", reviews)
    report = {
        "schema": "session-copilot-self-upgrade-cycle.v1",
        "feedback_records": len(feedback),
        "verdict_counts": dict(counts),
        "new_training_permitted_examples": len(candidates) - replay_examples,
        "replay_candidates": replay_examples,
        "combined_candidates": len(candidates),
        "families": len({c["family_id"] for c in candidates}),
        "concept_counts": dict(Counter(r["concept"] for r in reviews)),
        "ready_for_dataset_build": len(candidates) > replay_examples,
        "ready_for_training": False,
        "ready_for_promotion": False,
        "paid_calls": 0,
        "next_step": (
            "Build and evaluate the combined offline dataset; feedback never directly changes the active model."
            if replay_examples
            else "Add a reviewed replay corpus before training to avoid learning only from recent feedback."
        ),
    }
    write_jsonl(output / "cycle.jsonl", [report])
    return report
