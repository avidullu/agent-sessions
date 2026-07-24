"""Tests for the tracked, merge-aware rule evidence ledger (R1b, D17)."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.rule_extractor import RawRule, normalize_rule, polarity_of
from agent_sessions.rule_ledger import (
    EvidenceRecord,
    LedgerUpdate,
    build_evidence_records,
    default_ledger_path,
    load_ledger,
    merge_evidence_records,
    record_from_dict,
    record_to_dict,
    render_ledger_jsonl,
    stable_rule_id,
    update_ledger,
    write_ledger,
)

GITHUB_TOKEN = "ghp_" + "a" * 36


def make_rule(
    text: str,
    *,
    role: str = "user",
    session_id: str = "s-1",
    agent: str = "claude",
    project: str = "demo",
    novelty: str = "novel",
    mtime: float = 100.0,
) -> RawRule:
    normalized, tokens = normalize_rule(text)
    return RawRule(
        text=text,
        normalized=normalized,
        polarity=polarity_of(text),
        tokens=tokens,
        role=role,
        novelty=novelty,
        session_id=session_id,
        agent=agent,
        project=project,
        mtime=mtime,
    )


RULE_A = "Always run the full test suite before pushing changes."
RULE_B = "Never commit directly to the protected main branch here."


class TestStableRuleId:
    def test_deterministic(self) -> None:
        assert stable_rule_id("claude", "s", "user", "x y z") == stable_rule_id(
            "claude", "s", "user", "x y z"
        )

    def test_varies_by_component(self) -> None:
        base = stable_rule_id("claude", "s", "user", "x y z")
        assert base != stable_rule_id("codex", "s", "user", "x y z")
        assert base != stable_rule_id("claude", "s2", "user", "x y z")
        assert base != stable_rule_id("claude", "s", "assistant", "x y z")
        assert base != stable_rule_id("claude", "s", "user", "a b c")

    def test_prefixed(self) -> None:
        assert stable_rule_id("claude", "s", "user", "x y z").startswith("rule.")


class TestBuildEvidenceRecords:
    def test_basic_record(self) -> None:
        records, quarantined = build_evidence_records([make_rule(RULE_A)])
        assert quarantined == 0
        assert len(records) == 1
        assert records[0].occurrences == 1
        assert records[0].agent == "claude"
        assert records[0].novelty == "novel"

    def test_within_batch_repeats_increment_occurrences(self) -> None:
        records, _ = build_evidence_records([make_rule(RULE_A) for _ in range(3)])
        assert len(records) == 1
        assert records[0].occurrences == 3

    def test_distinct_roles_stay_separate(self) -> None:
        records, _ = build_evidence_records(
            [make_rule(RULE_A, role="user"), make_rule(RULE_A, role="assistant")]
        )
        assert len({r.id for r in records}) == 2

    def test_distinct_sessions_stay_separate(self) -> None:
        records, _ = build_evidence_records(
            [make_rule(RULE_A, session_id="s-1"), make_rule(RULE_A, session_id="s-2")]
        )
        assert len({r.id for r in records}) == 2

    def test_empty_normalized_skipped(self) -> None:
        # A rule whose text redacts to only stopwords/placeholders yields nothing.
        records, quarantined = build_evidence_records([make_rule("must not do so")])
        assert records == []
        assert quarantined == 0


class TestRedactionGate:
    def test_high_confidence_secret_is_quarantined(self) -> None:
        rule = make_rule(f"You must never paste {GITHUB_TOKEN} into the repo config.")
        records, quarantined = build_evidence_records([rule])
        assert records == []
        assert quarantined == 1

    def test_secret_never_reaches_the_ledger_text(self) -> None:
        # Mixed batch: the clean rule survives, the secret rule is quarantined,
        # and the token appears in no stored record.
        records, quarantined = build_evidence_records(
            [make_rule(RULE_A), make_rule(f"never share {GITHUB_TOKEN} in chat please")]
        )
        assert quarantined == 1
        assert len(records) == 1
        assert all(GITHUB_TOKEN not in record.text for record in records)

    def test_private_path_is_placeholdered_not_blocked(self) -> None:
        rule = make_rule("Always read /home/someone/notes before you start work.")
        records, quarantined = build_evidence_records([rule])
        assert quarantined == 0
        assert len(records) == 1
        assert "/home/someone" not in records[0].text
        assert "<path-1>" in records[0].text
        assert records[0].redaction_placeholders == 1

    def test_home_username_does_not_leak_into_normalized(self) -> None:
        # redaction-v1 placeholders the /home/<user> prefix; the private
        # username must not survive into the stored, tracked normalized form.
        records, _ = build_evidence_records(
            [make_rule("Always source /home/alice/env.sh before running the build.")]
        )
        assert "alice" not in records[0].normalized
        assert "alice" not in records[0].text


class TestCrossMachineMerge:
    def test_same_evidence_from_two_machines_collapses(self) -> None:
        # Same session_id + agent + role + rule, exported from two machines whose
        # only difference is the local project path — must collapse to one row.
        machine_a, _ = build_evidence_records([make_rule(RULE_B, project="repo-on-win")])
        machine_b, _ = build_evidence_records([make_rule(RULE_B, project="repo-on-wsl")])
        assert machine_a[0].id == machine_b[0].id
        merged = merge_evidence_records(machine_a, machine_b)
        assert len(merged) == 1

    def test_different_home_dirs_collapse_after_redaction(self) -> None:
        # Different absolute home paths redact to the same placeholder, so the
        # same rule sentence from two users collapses.
        alice, _ = build_evidence_records(
            [make_rule("Always source /home/alice/env.sh before running the build.")]
        )
        bob, _ = build_evidence_records(
            [make_rule("Always source /home/bob/env.sh before running the build.")]
        )
        assert alice[0].id == bob[0].id

    def test_current_wins_on_shared_id(self) -> None:
        first, _ = build_evidence_records([make_rule(RULE_A, mtime=100.0)])
        second, _ = build_evidence_records([make_rule(RULE_A, mtime=200.0)])
        merged = merge_evidence_records(first, second)
        assert len(merged) == 1
        assert merged[0].mtime == 200.0

    def test_merge_skips_idless_records(self) -> None:
        idless = EvidenceRecord(
            id="",
            text="x",
            normalized="x",
            polarity="positive",
            tokens=("x",),
            role="user",
            novelty="novel",
            session_id="s",
            agent="claude",
            project="p",
            mtime=1.0,
            occurrences=1,
            redaction_placeholders=0,
        )
        merged = merge_evidence_records([idless], [])
        assert merged == []


class TestSerialization:
    def test_round_trip(self) -> None:
        records, _ = build_evidence_records([make_rule(RULE_A)])
        (record,) = records
        assert record_from_dict(record_to_dict(record)) == record

    def test_from_dict_tolerates_missing_fields(self) -> None:
        record = record_from_dict({"id": "rule.abc"})
        assert record.id == "rule.abc"
        assert record.tokens == ()
        assert record.mtime == 0.0
        assert record.occurrences == 0

    def test_render_is_deterministic_with_trailing_newline(self) -> None:
        records, _ = build_evidence_records([make_rule(RULE_B), make_rule(RULE_A)])
        rendered = render_ledger_jsonl(records)
        assert rendered.endswith("\n")
        assert len(rendered.splitlines()) == 2
        # Order is by _sort_key and independent of input order.
        assert render_ledger_jsonl(list(reversed(records))) == rendered

    def test_render_empty(self) -> None:
        assert render_ledger_jsonl([]) == ""


class TestLedgerIO:
    def test_default_path(self) -> None:
        assert default_ledger_path(Path("/base")) == Path("/base/evidence/rules.jsonl")

    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        assert load_ledger(tmp_path / "nope.jsonl") == []

    def test_write_creates_parent_and_round_trips(self, tmp_path: Path) -> None:
        records, _ = build_evidence_records([make_rule(RULE_A)])
        path = tmp_path / "evidence" / "rules.jsonl"
        write_ledger(path, records)
        assert path.exists()
        assert load_ledger(path) == records


class TestUpdateLedger:
    def test_first_write_reports_added(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.jsonl"
        update = update_ledger(path, [make_rule(RULE_A), make_rule(RULE_B)])
        assert isinstance(update, LedgerUpdate)
        assert update.added == 2
        assert update.total == 2
        assert update.quarantined == 0
        assert load_ledger(path) == sorted(
            load_ledger(path), key=lambda r: (r.agent, r.project, r.normalized, r.id)
        )

    def test_re_running_same_batch_is_idempotent(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.jsonl"
        update_ledger(path, [make_rule(RULE_A)])
        second = update_ledger(path, [make_rule(RULE_A)])
        assert second.added == 0
        assert second.total == 1

    def test_new_machine_merges_into_committed_ledger(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.jsonl"
        update_ledger(path, [make_rule(RULE_A, agent="claude")])
        update = update_ledger(path, [make_rule(RULE_B, agent="codex")])
        assert update.added == 1
        assert update.total == 2
        agents = {record.agent for record in load_ledger(path)}
        assert agents == {"claude", "codex"}

    def test_quarantined_surfaced_and_excluded(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.jsonl"
        update = update_ledger(
            path,
            [make_rule(RULE_A), make_rule(f"never paste {GITHUB_TOKEN} anywhere here")],
        )
        assert update.quarantined == 1
        assert update.added == 1
        assert update.total == 1
