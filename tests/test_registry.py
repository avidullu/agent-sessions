"""Tests for agent_sessions.sources.registry."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.models import ExtractedSession
from agent_sessions.sources.registry import get_extractor, known_kinds, register


class TestRegister:
    def test_register_and_retrieve(self) -> None:
        @register("test-kind")
        def dummy_extractor(path: Path) -> ExtractedSession:
            return ExtractedSession(metadata={}, messages=[])

        extractor = get_extractor("test-kind")
        assert extractor is not None
        result = extractor(Path("/fake"))
        assert isinstance(result, ExtractedSession)

    def test_register_overwrites(self) -> None:
        @register("overwrite-kind")
        def first(path: Path) -> ExtractedSession:
            return ExtractedSession(metadata={"v": 1}, messages=[])

        @register("overwrite-kind")
        def second(path: Path) -> ExtractedSession:
            return ExtractedSession(metadata={"v": 2}, messages=[])

        extractor = get_extractor("overwrite-kind")
        assert extractor is not None
        result = extractor(Path("/fake"))
        assert result.metadata["v"] == 2

    def test_register_returns_function(self) -> None:
        @register("return-test")
        def my_func(path: Path) -> ExtractedSession:
            return ExtractedSession(metadata={}, messages=[])

        # The decorator should return the original function
        assert my_func is not None
        assert callable(my_func)


class TestGetExtractor:
    def test_unknown_kind_returns_none(self) -> None:
        assert get_extractor("nonexistent-kind-12345") is None

    def test_builtin_kinds_available(self) -> None:
        """After importing agent_sessions.sources, built-in kinds should be available."""
        kinds = known_kinds()
        expected = {
            "claude",
            "codex",
            "deepseek_request_dump",
            "gemini_antigravity",
            "grok",
        }
        assert expected.issubset(set(kinds))


class TestKnownKinds:
    def test_returns_sorted_tuple(self) -> None:
        kinds = known_kinds()
        assert isinstance(kinds, tuple)
        assert kinds == tuple(sorted(kinds))

    def test_includes_builtins(self) -> None:
        kinds = known_kinds()
        assert "claude" in kinds
        assert "codex" in kinds
