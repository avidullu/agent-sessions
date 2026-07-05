"""Tests for agent_sessions.models."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.models import ExtractedSession, SessionMessage, Source


class TestSource:
    def test_creation_defaults(self) -> None:
        source = Source(name="test", kind="claude", roots=(Path("/tmp"),))
        assert source.name == "test"
        assert source.kind == "claude"
        assert source.roots == (Path("/tmp"),)
        assert source.glob == "**/*"
        assert source.description == ""

    def test_creation_full(self) -> None:
        source = Source(
            name="full",
            kind="codex",
            roots=(Path("/a"), Path("/b")),
            glob="*.jsonl",
            description="A test source.",
        )
        assert source.name == "full"
        assert source.kind == "codex"
        assert len(source.roots) == 2
        assert source.glob == "*.jsonl"
        assert source.description == "A test source."

    def test_frozen_immutable(self) -> None:
        source = Source(name="test", kind="claude", roots=(Path("/tmp"),))
        try:
            source.name = "changed"  # type: ignore[misc]
        except Exception:
            pass  # Expected: FrozenInstanceError or similar
        assert source.name == "test"

    def test_equality(self) -> None:
        a = Source(name="x", kind="k", roots=(Path("/a"),))
        b = Source(name="x", kind="k", roots=(Path("/a"),))
        c = Source(name="y", kind="k", roots=(Path("/a"),))
        assert a == b
        assert a != c

    def test_hashable(self) -> None:
        source = Source(name="test", kind="claude", roots=(Path("/tmp"),))
        assert hash(source) is not None
        assert source in {source}


class TestSessionMessage:
    def test_creation_defaults(self) -> None:
        msg = SessionMessage(role="user", text="Hello")
        assert msg.role == "user"
        assert msg.text == "Hello"
        assert msg.timestamp == ""

    def test_creation_full(self) -> None:
        msg = SessionMessage(
            role="assistant", text="Hi", timestamp="2026-01-01T00:00:00Z"
        )
        assert msg.role == "assistant"
        assert msg.text == "Hi"
        assert msg.timestamp == "2026-01-01T00:00:00Z"

    def test_empty_text(self) -> None:
        msg = SessionMessage(role="system", text="")
        assert msg.text == ""


class TestExtractedSession:
    def test_creation(self) -> None:
        msgs = [SessionMessage(role="user", text="Hi")]
        meta = {"session_id": "abc"}
        session = ExtractedSession(metadata=meta, messages=msgs)
        assert session.metadata == meta
        assert session.messages == msgs

    def test_empty_messages(self) -> None:
        session = ExtractedSession(metadata={}, messages=[])
        assert session.messages == []
        assert session.metadata == {}

    def test_metadata_types(self) -> None:
        meta = {"session_id": "x", "count": 5, "tags": ["a", "b"]}
        session = ExtractedSession(metadata=meta, messages=[])
        assert session.metadata["session_id"] == "x"
        assert session.metadata["count"] == 5
        assert session.metadata["tags"] == ["a", "b"]
