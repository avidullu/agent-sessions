"""Tests for evidence-ledger clustering and contradiction detection (R2, D19)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from agent_sessions.rule_clusterer import (
    ClusteredRule,
    ContradictionPair,
    clean_token,
    cluster_ledger,
    cluster_rules,
    clustered_rule_to_dict,
    find_contradictions,
    jaccard,
)
from agent_sessions.rule_ledger import EvidenceRecord, write_ledger

NOW = dt.datetime(2033, 5, 18, tzinfo=dt.UTC)
RECENT = NOW.timestamp() - 10 * 86400  # 10 days old → recency weight 1.0


def rec(
    tokens: tuple[str, ...],
    *,
    polarity: str = "negative",
    novelty: str = "novel",
    session_id: str = "s1",
    agent: str = "claude",
    project: str = "demo",
    mtime: float = RECENT,
    rid: str | None = None,
    text: str | None = None,
) -> EvidenceRecord:
    normalized = " ".join(tokens)
    return EvidenceRecord(
        id=rid or f"rule.{agent}.{session_id}.{normalized}",
        text=text or normalized,
        normalized=normalized,
        polarity=polarity,
        tokens=tokens,
        role="user",
        novelty=novelty,
        session_id=session_id,
        agent=agent,
        project=project,
        mtime=mtime,
        occurrences=1,
        redaction_placeholders=0,
    )


class TestHelpers:
    def test_clean_token_strips_edges_keeps_internal(self) -> None:
        assert clean_token("repo.") == "repo"
        assert clean_token("index.jsonl") == "index.jsonl"
        assert clean_token("(main)") == "main"

    def test_jaccard(self) -> None:
        assert jaccard(frozenset("ab"), frozenset("ab")) == 1.0
        assert jaccard(frozenset("ab"), frozenset("cd")) == 0.0
        assert jaccard(frozenset(), frozenset("a")) == 0.0


class TestClustering:
    def test_paraphrases_cluster_together(self) -> None:
        records = [
            rec(("commit", "directly", "main", "branch"), rid="a"),
            rec(("commit", "main", "branch"), rid="b"),
        ]
        clusters = cluster_rules(records, now=NOW)
        assert len(clusters) == 1
        assert set(clusters[0].member_ids) == {"a", "b"}

    def test_distinct_topics_stay_separate(self) -> None:
        records = [
            rec(("commit", "main", "branch"), rid="a"),
            rec(("run", "full", "test", "suite"), rid="b"),
        ]
        assert len(cluster_rules(records, now=NOW)) == 2

    def test_trailing_punctuation_clusters_with_bare_token(self) -> None:
        # The `repo.`-vs-`repo` artifact flagged in R1's review, fixed here.
        records = [
            rec(("commit", "main", "repo."), rid="a"),
            rec(("commit", "main", "repo"), rid="b"),
        ]
        clusters = cluster_rules(records, now=NOW)
        assert len(clusters) == 1
        assert "repo" in clusters[0].topic_tokens
        assert "repo." not in clusters[0].topic_tokens

    def test_deterministic_regardless_of_input_order(self) -> None:
        records = [
            rec(("commit", "main", "branch"), rid="a"),
            rec(("run", "full", "test", "suite"), rid="b"),
            rec(("commit", "branch"), rid="c"),
        ]
        assert cluster_rules(records, now=NOW) == cluster_rules(list(reversed(records)), now=NOW)

    def test_same_session_two_roles_counts_one_session(self) -> None:
        records = [
            rec(("commit", "main", "branch"), session_id="s1", rid="a"),
            rec(("commit", "main", "branch"), session_id="s1", rid="b"),
        ]
        (cluster,) = cluster_rules(records, now=NOW)
        assert cluster.session_count == 1
        assert cluster.novel_sessions == 1
        assert set(cluster.member_ids) == {"a", "b"}

    def test_empty_input(self) -> None:
        assert cluster_rules([], now=NOW) == []

    def test_tokenless_records_dropped(self) -> None:
        # A record whose only token is punctuation contributes nothing.
        assert cluster_rules([rec((".",), rid="a")], now=NOW) == []


class TestScoring:
    def test_frequency_is_distinct_novel_sessions(self) -> None:
        records = [
            rec(("deploy", "prod", "friday"), session_id=f"s{i}", rid=f"r{i}") for i in range(3)
        ]
        (cluster,) = cluster_rules(records, now=NOW)
        assert cluster.novel_sessions == 3
        assert cluster.score == 3.0  # 3 sessions × recency 1.0 × single-agent factor 1.0

    def test_cross_agent_factor_rewards_multiple_qualifying_agents(self) -> None:
        records = []
        for agent in ("claude", "codex"):
            for i in range(2):  # 2 sessions each → both agents qualify (≥2)
                records.append(rec(("never", "force", "push"), session_id=f"{agent}{i}", agent=agent, rid=f"{agent}{i}"))
        (cluster,) = cluster_rules(records, now=NOW)
        assert cluster.novel_sessions == 4
        assert cluster.agent_count == 2
        assert cluster.score == 6.0  # 4 × 1.0 × (1 + 0.5×(2-1)) = 4 × 1.5

    def test_single_session_rare_agent_gets_no_cross_bonus(self) -> None:
        records = [
            rec(("shared", "topic", "rule"), session_id="c0", agent="claude", rid="c0"),
            rec(("shared", "topic", "rule"), session_id="c1", agent="claude", rid="c1"),
            rec(("shared", "topic", "rule"), session_id="g0", agent="grok", rid="g0"),  # lone grok
        ]
        (cluster,) = cluster_rules(records, now=NOW)
        # claude qualifies (2), grok does not (1) → effective agents = 1, factor 1.0
        assert cluster.novel_sessions == 3
        assert cluster.score == 3.0
        assert dict(cluster.per_agent_sessions) == {"claude": 2, "grok": 1}

    def test_per_agent_breakdown_disclosed(self) -> None:
        records = [
            rec(("audit", "trail", "kept"), session_id="c0", agent="claude", rid="c0"),
            rec(("audit", "trail", "kept"), session_id="d0", agent="deepseek", rid="d0"),
        ]
        (cluster,) = cluster_rules(records, now=NOW)
        assert dict(cluster.per_agent_sessions) == {"claude": 1, "deepseek": 1}
        assert cluster.agents == ("claude", "deepseek")


class TestEchoDiscipline:
    def test_echo_only_cluster_scores_zero(self) -> None:
        records = [
            rec(("published", "rule", "reechoed"), session_id=f"s{i}", novelty="echo", rid=f"r{i}")
            for i in range(4)
        ]
        (cluster,) = cluster_rules(records, now=NOW)
        assert cluster.novel_sessions == 0
        assert cluster.echo_sessions == 4
        assert cluster.score == 0.0

    def test_mixed_cluster_counts_only_novel_for_score(self) -> None:
        records = [
            rec(("branch", "before", "commit"), session_id="n0", novelty="novel", rid="n0"),
            rec(("branch", "before", "commit"), session_id="n1", novelty="novel", rid="n1"),
            rec(("branch", "before", "commit"), session_id="e0", novelty="echo", rid="e0"),
        ]
        (cluster,) = cluster_rules(records, now=NOW)
        assert cluster.novel_sessions == 2
        assert cluster.echo_sessions == 1
        assert cluster.session_count == 3
        assert cluster.score == 2.0  # single agent


class TestContradictions:
    def test_same_topic_opposite_polarity_flagged(self) -> None:
        records = [
            rec(("squash", "merge", "branches"), polarity="positive", rid="p"),
            rec(("squash", "merge", "branches"), polarity="negative", rid="n"),
        ]
        clusters = cluster_rules(records, now=NOW)
        assert len(clusters) == 2
        pairs = find_contradictions(clusters)
        assert len(pairs) == 1
        pair = pairs[0]
        assert isinstance(pair, ContradictionPair)
        assert pair.overlap == 1.0
        assert pair.shared_tokens == ("branches", "merge", "squash")
        # positive/negative correctly assigned by polarity
        pos = next(c for c in clusters if c.polarity == "positive")
        neg = next(c for c in clusters if c.polarity == "negative")
        assert pair.positive_id == pos.id
        assert pair.negative_id == neg.id

    def test_same_polarity_is_not_a_contradiction(self) -> None:
        records = [
            rec(("squash", "merge", "branches"), polarity="negative", session_id="s0", rid="a"),
            rec(("squash", "merge", "branches"), polarity="negative", session_id="s1", rid="b"),
        ]
        clusters = cluster_rules(records, now=NOW)
        assert find_contradictions(clusters) == []

    def test_unrelated_opposite_polarity_not_flagged(self) -> None:
        records = [
            rec(("always", "sign", "commits"), polarity="positive", rid="a"),
            rec(("never", "delete", "logs"), polarity="negative", rid="b"),
        ]
        clusters = cluster_rules(records, now=NOW)
        assert find_contradictions(clusters) == []


class TestSerializationAndIntegration:
    def test_to_dict_shape(self) -> None:
        (cluster,) = cluster_rules([rec(("commit", "main", "branch"))], now=NOW)
        d = clustered_rule_to_dict(cluster)
        assert d["polarity"] == "negative"
        assert isinstance(d["per_agent_sessions"], dict)
        assert set(d) >= {"id", "canonical_text", "topic_tokens", "score", "novel_sessions", "member_ids"}

    def test_cluster_ledger_reads_and_returns_pair(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.jsonl"
        records = [
            rec(("squash", "merge", "branches"), polarity="positive", rid="p"),
            rec(("squash", "merge", "branches"), polarity="negative", rid="n"),
            rec(("run", "tests", "before", "push"), session_id="s2", rid="t"),
        ]
        write_ledger(path, records)
        clusters, contradictions = cluster_ledger(path, now=NOW)
        assert len(clusters) == 3
        assert len(contradictions) == 1
        assert all(isinstance(c, ClusteredRule) for c in clusters)

    def test_cluster_ledger_missing_file(self, tmp_path: Path) -> None:
        clusters, contradictions = cluster_ledger(tmp_path / "nope.jsonl", now=NOW)
        assert clusters == []
        assert contradictions == []
