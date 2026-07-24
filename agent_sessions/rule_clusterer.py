"""Cluster evidence-ledger rules and surface contradictions (R2, D19).

Deterministic, no LLM (D1). Reads :class:`~agent_sessions.rule_ledger.EvidenceRecord`
rows and groups them by **(polarity, topic-token overlap)** — never by raw edit
distance, which merges opposites and splits paraphrases (the failure D19 fixes).
Two rules cluster when they share a polarity and their cleaned topic-token sets
overlap past a threshold; edit distance is available only as a downstream
tie-breaker, not a clustering criterion.

The clusterer produces two outputs the rest of the pipeline consumes:

- **clusters** (:class:`ClusteredRule`): scored, deduplicated rules with a
  disclosed per-agent breakdown, so a cross-agent "bonus" can never quietly
  imply five-agent consensus on a corpus that is really claude+deepseek (§3.4).
- **contradictions** (:class:`ContradictionPair`): same topic, opposite polarity
  — the flagship signal (§1.3 #4) that feeds `baseline lint`'s P6 check and
  answers "always squash" vs "never squash" without a human noticing first.

Echo discipline (D18): records tagged ``echo`` (instruction-file text that rode
into a session's context) still cluster, but only ``novel`` evidence counts
toward frequency and the cross-agent factor — so a published rule that every
later session re-quotes cannot inflate its own score.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .rule_extractor import NOVELTY_NOVEL
from .rule_ledger import EvidenceRecord, load_ledger
from .utils import session_recency_weight

#: Cleaned-token Jaccard at or above which two same-polarity rules share a cluster.
JACCARD_CLUSTER = 0.5
#: Topic-token Jaccard at or above which opposite-polarity clusters are a contradiction.
JACCARD_CONTRA = 0.5
#: Per extra qualifying agent, the cross-agent factor grows by this much.
CROSS_AGENT_BONUS = 0.5
#: An agent must carry at least this many novel sessions to count toward the
#: cross-agent factor — damps a single drive-by session from a rare agent (§3.4).
MIN_SESSIONS_PER_AGENT_FOR_CROSS = 2
#: Tokens shorter than this after end-punctuation stripping are dropped as noise.
MIN_TOKEN_LEN = 2
#: Stripped from token ends so ``repo.`` clusters with ``repo`` — the trailing-
#: punctuation artifact flagged in R1's review, resolved here at the clusterer.
_TOKEN_EDGE_PUNCT = ".,;:!?()[]{}\"'`…"


@dataclass(frozen=True)
class ClusteredRule:
    """A scored cluster of equivalent rules with a disclosed per-agent breakdown."""

    id: str
    canonical_text: str
    polarity: str
    topic_tokens: tuple[str, ...]
    session_count: int
    novel_sessions: int
    echo_sessions: int
    agent_count: int
    agents: tuple[str, ...]
    per_agent_sessions: tuple[tuple[str, int], ...]
    projects: tuple[str, ...]
    score: float
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContradictionPair:
    """Two clusters on the same topic with opposite polarity (D19)."""

    positive_id: str
    negative_id: str
    positive_text: str
    negative_text: str
    shared_tokens: tuple[str, ...]
    overlap: float


def clean_token(token: str) -> str:
    """Strip surrounding punctuation (keeps internal, e.g. ``index.jsonl``)."""
    return token.strip(_TOKEN_EDGE_PUNCT)


def cluster_tokens(record: EvidenceRecord) -> frozenset[str]:
    """The record's topic tokens, end-punctuation-stripped and length-filtered."""
    out: set[str] = set()
    for token in record.tokens:
        cleaned = clean_token(token)
        if len(cleaned) >= MIN_TOKEN_LEN:
            out.add(cleaned)
    return frozenset(out)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _session_key(record: EvidenceRecord) -> str:
    """A stable per-session key; falls back to the record id when session_id is blank.

    Dedup-safe in the fallback: an id embeds agent+session+role+normalized, so two
    genuinely distinct blank-session records never collapse into one session.
    """
    return record.session_id or record.id


@dataclass
class _Cluster:
    polarity: str
    seed_tokens: frozenset[str]
    members: list[EvidenceRecord]


def _cluster_id(polarity: str, topic_tokens: tuple[str, ...]) -> str:
    # Snapshot-stable, not incrementally stable: the id hashes the cluster's full
    # (union) topic-token set, so adding a member can change it. That is fine —
    # clustering runs once per ledger snapshot, never incrementally.
    payload = f"{polarity}|{' '.join(topic_tokens)}"
    return f"rule-cluster.{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


def _canonical_text(records: list[EvidenceRecord]) -> str:
    """Most-recurring member text, tie-broken by shortest then lexicographic."""
    by_text: dict[str, int] = {}
    for record in records:
        by_text[record.text] = by_text.get(record.text, 0) + 1
    return min(by_text, key=lambda text: (-by_text[text], len(text), text))


def _finalize(cluster: _Cluster, now: dt.datetime | None) -> ClusteredRule:
    members = cluster.members
    novel = [m for m in members if m.novelty == NOVELTY_NOVEL]
    echo = [m for m in members if m.novelty != NOVELTY_NOVEL]

    all_sessions = {_session_key(m) for m in members}
    novel_sessions = {_session_key(m) for m in novel}
    echo_sessions = {_session_key(m) for m in echo}

    per_agent_all: dict[str, set[str]] = {}
    per_agent_novel: dict[str, set[str]] = {}
    for m in members:
        if m.agent:
            per_agent_all.setdefault(m.agent, set()).add(_session_key(m))
    for m in novel:
        if m.agent:
            per_agent_novel.setdefault(m.agent, set()).add(_session_key(m))

    topic_tokens: set[str] = set()
    for m in members:
        topic_tokens |= cluster_tokens(m)
    topic = tuple(sorted(topic_tokens))

    basis = novel or members
    recency = max(
        (session_recency_weight({"mtime": m.mtime}, now=now) for m in basis),
        default=0.0,
    )
    qualifying_agents = sum(
        1 for sessions in per_agent_novel.values() if len(sessions) >= MIN_SESSIONS_PER_AGENT_FOR_CROSS
    )
    effective_agents = max(qualifying_agents, 1) if per_agent_novel else 0
    cross_agent_factor = 1.0 + CROSS_AGENT_BONUS * (effective_agents - 1) if effective_agents else 0.0
    score = len(novel_sessions) * recency * cross_agent_factor

    return ClusteredRule(
        id=_cluster_id(cluster.polarity, topic),
        canonical_text=_canonical_text(basis),
        polarity=cluster.polarity,
        topic_tokens=topic,
        session_count=len(all_sessions),
        novel_sessions=len(novel_sessions),
        echo_sessions=len(echo_sessions),
        agent_count=len(per_agent_all),
        agents=tuple(sorted(per_agent_all)),
        per_agent_sessions=tuple(sorted((a, len(s)) for a, s in per_agent_all.items())),
        projects=tuple(sorted({m.project for m in members if m.project})),
        score=round(score, 4),
        member_ids=tuple(sorted(m.id for m in members)),
    )


def cluster_rules(records: Iterable[EvidenceRecord], *, now: dt.datetime | None = None) -> list[ClusteredRule]:
    """Group ledger records into scored clusters (deterministic, order-independent).

    Records are processed in a fixed (polarity, normalized, id) order and each is
    placed into the first existing same-polarity cluster whose *seed* token set it
    overlaps past :data:`JACCARD_CLUSTER`, else it seeds a new cluster. Seeding on
    the first member (not the growing union) keeps clusters from drifting.
    """
    prepared = [(record, cluster_tokens(record)) for record in records]
    prepared = [(record, tokens) for record, tokens in prepared if tokens]
    prepared.sort(key=lambda item: (item[0].polarity, item[0].normalized, item[0].id))

    clusters: list[_Cluster] = []
    for record, tokens in prepared:
        placed = False
        for cluster in clusters:
            if cluster.polarity == record.polarity and jaccard(cluster.seed_tokens, tokens) >= JACCARD_CLUSTER:
                cluster.members.append(record)
                placed = True
                break
        if not placed:
            clusters.append(_Cluster(polarity=record.polarity, seed_tokens=tokens, members=[record]))

    finalized = [_finalize(cluster, now) for cluster in clusters]
    finalized.sort(key=lambda c: (-c.score, c.canonical_text, c.id))
    return finalized


def find_contradictions(clusters: list[ClusteredRule]) -> list[ContradictionPair]:
    """Pairs of clusters — same topic, opposite polarity — for human resolution (D19).

    O(n²) over clusters, negligible at the tens-of-clusters scale a ledger snapshot
    produces; revisit only if cluster counts reach the thousands.
    """
    pairs: list[ContradictionPair] = []
    for i, left in enumerate(clusters):
        for right in clusters[i + 1 :]:
            if left.polarity == right.polarity:
                continue
            overlap = jaccard(frozenset(left.topic_tokens), frozenset(right.topic_tokens))
            if overlap < JACCARD_CONTRA:
                continue
            positive, negative = (left, right) if left.polarity == "positive" else (right, left)
            shared = tuple(sorted(set(left.topic_tokens) & set(right.topic_tokens)))
            pairs.append(
                ContradictionPair(
                    positive_id=positive.id,
                    negative_id=negative.id,
                    positive_text=positive.canonical_text,
                    negative_text=negative.canonical_text,
                    shared_tokens=shared,
                    overlap=round(overlap, 4),
                )
            )
    pairs.sort(key=lambda p: (-p.overlap, p.positive_id, p.negative_id))
    return pairs


def clustered_rule_to_dict(rule: ClusteredRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "canonical_text": rule.canonical_text,
        "polarity": rule.polarity,
        "topic_tokens": list(rule.topic_tokens),
        "session_count": rule.session_count,
        "novel_sessions": rule.novel_sessions,
        "echo_sessions": rule.echo_sessions,
        "agent_count": rule.agent_count,
        "agents": list(rule.agents),
        "per_agent_sessions": dict(rule.per_agent_sessions),
        "projects": list(rule.projects),
        "score": rule.score,
        "member_ids": list(rule.member_ids),
    }


def cluster_ledger(
    path: Path, *, now: dt.datetime | None = None
) -> tuple[list[ClusteredRule], list[ContradictionPair]]:
    """Load the evidence ledger at ``path`` and return (clusters, contradictions)."""
    records = load_ledger(path)
    clusters = cluster_rules(records, now=now)
    return clusters, find_contradictions(clusters)
