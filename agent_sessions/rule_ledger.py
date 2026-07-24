"""Tracked, merge-aware evidence ledger for mined rules (R1b, D17).

The ledger is the cross-machine home for rule evidence: `RawRule`s mined per
session at export time (R1) are redacted, deduplicated by a stable id, and
appended to a git-tracked ``baseline/evidence/rules.jsonl`` that union-merges
across machines exactly like ``baseline/handoffs/index.jsonl`` and
``archive/index.jsonl``. Because the ledger — not any single machine's local
transcript bodies — is what the clusterer/scorer read, scores stop depending on
which machine happens to hold a body (F2 in issue #99).

Two invariants:

- **Redaction-gated (D17, redaction-v1).** Every rule's text passes
  :func:`agent_sessions.baseline_redaction.redact_text` before it can enter the
  ledger. A high-confidence secret **quarantines** the rule (dropped, counted —
  fail-soft, mirroring D11), never aborting the run. Path/email placeholders are
  applied to the stored text, and the stored ``normalized`` form and stable id
  are recomputed from the *redacted* text so nothing raw leaks through a derived
  field.
- **Stable identity.** A rule's id is a hash of ``(agent, session_id, role,
  normalized)`` so the same evidence exported from two machines (Windows + WSL,
  different absolute paths, same ``session_id``) collapses to one row, while
  distinct sessions, agents, or roles stay separate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .baseline_redaction import redact_text
from .rule_extractor import RawRule, normalize_rule, polarity_of
from .utils import read_jsonl_dicts

LEDGER_RELATIVE_PATH = Path("evidence") / "rules.jsonl"


@dataclass(frozen=True)
class EvidenceRecord:
    """One redacted, deduplicated piece of rule evidence in the ledger.

    ``occurrences`` is a **within-batch** count — repeats of this rule inside a
    single :func:`build_evidence_records` call — not a cumulative cross-run
    total. Because :func:`merge_evidence_records` is current-wins (not additive),
    a rule seen in N separate exports still stores only the last run's count.
    Cumulative frequency (how many distinct sessions/records carry a rule) is a
    clustering signal that must be counted from the ledger records themselves
    (R2's job), never read off this field.
    """

    id: str
    text: str
    normalized: str
    polarity: str
    tokens: tuple[str, ...]
    role: str
    novelty: str
    session_id: str
    agent: str
    project: str
    mtime: float
    occurrences: int
    redaction_placeholders: int


@dataclass(frozen=True)
class LedgerUpdate:
    """Summary of an :func:`update_ledger` run (for the CLI/export report)."""

    path: Path
    total: int
    added: int
    quarantined: int


def default_ledger_path(baseline_root: Path) -> Path:
    return baseline_root / LEDGER_RELATIVE_PATH


def stable_rule_id(agent: str, session_id: str, role: str, normalized: str) -> str:
    digest = hashlib.sha256(f"{agent}:{session_id}:{role}:{normalized}".encode()).hexdigest()[:12]
    return f"rule.{digest}"


def build_evidence_records(rules: Iterable[RawRule]) -> tuple[list[EvidenceRecord], int]:
    """Redact, quarantine-on-block, and dedup a batch of rules by stable id.

    Returns ``(records, quarantined_count)``. Within-session repeats of the same
    redacted rule collapse into one record whose ``occurrences`` is the count.
    """
    by_id: dict[str, EvidenceRecord] = {}
    quarantined = 0
    for rule in rules:
        result = redact_text(rule.text)
        if result.blocked:
            quarantined += 1
            continue
        normalized, tokens = normalize_rule(result.redacted_text)
        if not normalized:
            continue
        rid = stable_rule_id(rule.agent, rule.session_id, rule.role, normalized)
        previous = by_id.get(rid)
        occurrences = (previous.occurrences if previous else 0) + 1
        by_id[rid] = EvidenceRecord(
            id=rid,
            text=result.redacted_text,
            normalized=normalized,
            polarity=polarity_of(result.redacted_text),
            tokens=tokens,
            role=rule.role,
            novelty=rule.novelty,
            session_id=rule.session_id,
            agent=rule.agent,
            project=rule.project,
            mtime=rule.mtime,
            occurrences=occurrences,
            redaction_placeholders=len(result.placeholders),
        )
    return list(by_id.values()), quarantined


def record_to_dict(record: EvidenceRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "text": record.text,
        "normalized": record.normalized,
        "polarity": record.polarity,
        "tokens": list(record.tokens),
        "role": record.role,
        "novelty": record.novelty,
        "session_id": record.session_id,
        "agent": record.agent,
        "project": record.project,
        "mtime": record.mtime,
        "occurrences": record.occurrences,
        "redaction_placeholders": record.redaction_placeholders,
    }


def record_from_dict(data: dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        id=str(data.get("id", "")),
        text=str(data.get("text", "")),
        normalized=str(data.get("normalized", "")),
        polarity=str(data.get("polarity", "")),
        tokens=tuple(str(token) for token in data.get("tokens", [])),
        role=str(data.get("role", "")),
        novelty=str(data.get("novelty", "")),
        session_id=str(data.get("session_id", "")),
        agent=str(data.get("agent", "")),
        project=str(data.get("project", "")),
        mtime=float(data.get("mtime", 0.0) or 0.0),
        occurrences=int(data.get("occurrences", 0) or 0),
        redaction_placeholders=int(data.get("redaction_placeholders", 0) or 0),
    )


def _sort_key(record: EvidenceRecord) -> tuple[str, str, str, str]:
    return (record.agent, record.project, record.normalized, record.id)


def load_ledger(path: Path) -> list[EvidenceRecord]:
    if not path.exists():
        return []
    return [record_from_dict(data) for data in read_jsonl_dicts(path, label=str(path))]


def merge_evidence_records(
    existing: list[EvidenceRecord],
    current: list[EvidenceRecord],
) -> list[EvidenceRecord]:
    """Union-merge by stable id; the current run wins for a shared id.

    Same id means the same evidence (same agent/session/role/rule), so a re-export
    or a second machine's copy replaces rather than accumulates.
    """
    merged = {record.id: record for record in existing if record.id}
    for record in current:
        if record.id:
            merged[record.id] = record
    return sorted(merged.values(), key=_sort_key)


def render_ledger_jsonl(records: list[EvidenceRecord]) -> str:
    lines = [
        json.dumps(record_to_dict(record), ensure_ascii=False, sort_keys=True)
        for record in sorted(records, key=_sort_key)
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def write_ledger(path: Path, records: list[EvidenceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ledger_jsonl(records), encoding="utf-8")


def update_ledger(path: Path, rules: Iterable[RawRule]) -> LedgerUpdate:
    """Fold a batch of freshly mined rules into the tracked ledger on disk."""
    existing = load_ledger(path)
    current, quarantined = build_evidence_records(rules)
    existing_ids = {record.id for record in existing}
    added = sum(1 for record in current if record.id not in existing_ids)
    merged = merge_evidence_records(existing, current)
    write_ledger(path, merged)
    return LedgerUpdate(path=path, total=len(merged), added=added, quarantined=quarantined)
