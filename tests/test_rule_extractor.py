"""Tests for role-aware imperative-rule extraction (R1, D18)."""

from __future__ import annotations

import pytest

from agent_sessions.models import ExtractedSession, SessionMessage
from agent_sessions.rule_extractor import (
    NOVELTY_ECHO,
    NOVELTY_NOVEL,
    POLARITY_NEGATIVE,
    POLARITY_POSITIVE,
    RawRule,
    build_known_normals,
    extract_rules,
    iter_imperative_sentences,
    normalize_rule,
    polarity_of,
    project_from_metadata,
    session_id_from_metadata,
    strip_marker_blocks,
)

RULE_NEVER = "Never commit directly to the main branch of this repo."
RULE_ALWAYS = "Always run the full test suite before pushing changes."
PROSE = "The weather is nice today and the build finished quickly again."


def make_session(messages: list[SessionMessage], **metadata: str) -> ExtractedSession:
    return ExtractedSession(metadata=dict(metadata), messages=messages)


class TestSentenceIteration:
    def test_finds_imperative_sentences(self) -> None:
        text = f"{PROSE} {RULE_NEVER} {RULE_ALWAYS}"
        found = iter_imperative_sentences(text)
        assert found == [RULE_NEVER, RULE_ALWAYS]

    def test_ignores_non_imperative_prose(self) -> None:
        assert iter_imperative_sentences(PROSE) == []

    @pytest.mark.parametrize(
        "line",
        [
            "| never | a table row with cue words |",
            "# never trust a heading",
            "> never quote blocks either",
            "never `a` `b` `c` `d` `e` too much inline code here",
            "must go",  # below MIN_SENTENCE_LEN
            "never " + "x" * 300,  # above MAX_SENTENCE_LEN
        ],
    )
    def test_noise_filters(self, line: str) -> None:
        assert iter_imperative_sentences(line) == []

    def test_splits_on_newlines(self) -> None:
        text = f"{RULE_NEVER}\n{RULE_ALWAYS}\n"
        assert iter_imperative_sentences(text) == [RULE_NEVER, RULE_ALWAYS]


class TestPolarity:
    @pytest.mark.parametrize(
        "sentence, expected",
        [
            (RULE_NEVER, POLARITY_NEGATIVE),
            ("You must not push directly to main today.", POLARITY_NEGATIVE),
            ("Please don't merge without a green CI run.", POLARITY_NEGATIVE),
            ("You should not skip the coverage gate.", POLARITY_NEGATIVE),
            (RULE_ALWAYS, POLARITY_POSITIVE),
            ("You must open a pull request for review.", POLARITY_POSITIVE),
            ("You should rebase onto the remote base branch.", POLARITY_POSITIVE),
        ],
    )
    def test_polarity(self, sentence: str, expected: str) -> None:
        assert polarity_of(sentence) == expected


class TestNormalization:
    def test_lowercases_drops_stopwords_sorts_tokens(self) -> None:
        normalized, tokens = normalize_rule("Never COMMIT directly to the Main branch!")
        assert normalized == "commit directly main branch"
        assert tokens == ("branch", "commit", "directly", "main")

    def test_deterministic(self) -> None:
        assert normalize_rule(RULE_ALWAYS) == normalize_rule(RULE_ALWAYS)


class TestMarkerBlocks:
    def test_strips_generated_blocks(self) -> None:
        text = (
            "<!-- baseline:begin id=\"x\" -->\n"
            f"{RULE_NEVER}\n"
            "<!-- baseline:end id=\"x\" -->\n"
            f"{RULE_ALWAYS}"
        )
        assert iter_imperative_sentences(strip_marker_blocks(text)) == [RULE_ALWAYS]


class TestKnownNormals:
    def test_matches_normalized_instruction_text(self) -> None:
        known = build_known_normals([f"Intro prose here.\n{RULE_NEVER}\n"])
        normalized, _ = normalize_rule(RULE_NEVER)
        assert normalized in known

    def test_marker_content_excluded_from_known_set(self) -> None:
        known = build_known_normals(
            [f"<!-- baseline:begin -->{RULE_NEVER}<!-- baseline:end -->"]
        )
        assert known == frozenset()


class TestProvenanceHelpers:
    def test_session_id(self) -> None:
        assert session_id_from_metadata({"session_id": "abc-123"}) == "abc-123"
        assert session_id_from_metadata({}) == ""

    @pytest.mark.parametrize(
        "cwd, expected",
        [
            ("C:\\Users\\someone\\Projects\\My-Repo", "my-repo"),
            ("C:/Users/someone/Projects/My-Repo", "my-repo"),
            ("/home/someone/projects/agent-sessions", "agent-sessions"),
            ("/home/someone/projects/agent-sessions/", "agent-sessions"),
            ("", ""),
        ],
    )
    def test_project_from_cwd(self, cwd: str, expected: str) -> None:
        assert project_from_metadata({"cwd": cwd}) == expected

    def test_project_missing_cwd(self) -> None:
        assert project_from_metadata({}) == ""


class TestExtractRules:
    def test_role_and_provenance_captured(self) -> None:
        session = make_session(
            [
                SessionMessage(role="user", text=RULE_NEVER),
                SessionMessage(role="assistant", text=RULE_ALWAYS),
            ],
            session_id="s-1",
            cwd="/home/someone/projects/demo",
        )
        rules = extract_rules(session, agent="claude", mtime=123.0)
        assert [r.role for r in rules] == ["user", "assistant"]
        assert all(r.session_id == "s-1" for r in rules)
        assert all(r.agent == "claude" for r in rules)
        assert all(r.project == "demo" for r in rules)
        assert all(r.mtime == 123.0 for r in rules)
        assert all(isinstance(r, RawRule) for r in rules)

    def test_novelty_echo_for_known_instruction_text(self) -> None:
        session = make_session(
            [SessionMessage(role="user", text=f"{RULE_NEVER} {RULE_ALWAYS}")]
        )
        rules = extract_rules(
            session,
            agent="codex",
            mtime=1.0,
            known_instruction_texts=[f"Working agreement:\n{RULE_NEVER}"],
        )
        by_text = {r.text: r.novelty for r in rules}
        assert by_text[RULE_NEVER] == NOVELTY_ECHO
        assert by_text[RULE_ALWAYS] == NOVELTY_NOVEL

    def test_marker_blocks_never_mined(self) -> None:
        session = make_session(
            [
                SessionMessage(
                    role="user",
                    text=f"<!-- baseline:begin -->{RULE_NEVER}<!-- baseline:end -->",
                )
            ]
        )
        assert extract_rules(session, agent="claude", mtime=1.0) == []

    def test_too_few_topic_tokens_skipped(self) -> None:
        session = make_session([SessionMessage(role="user", text="You must not do it.")])
        assert extract_rules(session, agent="claude", mtime=1.0) == []

    def test_missing_role_becomes_unknown(self) -> None:
        session = make_session([SessionMessage(role="", text=RULE_NEVER)])
        rules = extract_rules(session, agent="grok", mtime=1.0)
        assert [r.role for r in rules] == ["unknown"]

    def test_deterministic_order_and_output(self) -> None:
        session = make_session(
            [
                SessionMessage(role="user", text=f"{RULE_ALWAYS} {RULE_NEVER}"),
                SessionMessage(role="assistant", text=RULE_NEVER),
            ]
        )
        first = extract_rules(session, agent="claude", mtime=9.0)
        second = extract_rules(session, agent="claude", mtime=9.0)
        assert first == second
        assert [r.text for r in first] == [RULE_ALWAYS, RULE_NEVER, RULE_NEVER]

    def test_polarity_and_tokens_flow_through(self) -> None:
        session = make_session([SessionMessage(role="user", text=RULE_NEVER)])
        (rule,) = extract_rules(session, agent="claude", mtime=1.0)
        assert rule.polarity == POLARITY_NEGATIVE
        assert "main" in rule.tokens
        assert rule.normalized == "commit directly main branch repo."
