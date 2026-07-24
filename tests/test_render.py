"""Tests for agent_sessions.render."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from agent_sessions.models import ExtractedSession, SessionMessage, Source
from agent_sessions.render import (
    markdown_for_session,
    modified_timestamp,
    write_pdf,
)


class TestMarkdownForSession:
    def test_basic_session(self, tmp_path: Path) -> None:
        source = Source(name="test-claude", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(
            metadata={"session_id": "abc-123"},
            messages=[
                SessionMessage(role="user", text="Hello"),
                SessionMessage(role="assistant", text="Hi there!"),
            ],
        )
        md = markdown_for_session(
            source,
            session_file,
            session,
            digest="abc123",
            imported_at="2026-01-01T00:00:00+00:00",
        )

        assert "# test-claude / abc-123" in md
        assert "## Metadata" in md
        assert "- Source: `test-claude`" in md
        assert "- Kind: `claude`" in md
        assert "- SHA-256: `abc123`" in md
        assert "- Imported at: `2026-01-01T00:00:00+00:00`" in md
        assert "## Transcript" in md
        assert "### 1. user" in md
        assert "Hello" in md
        assert "### 2. assistant" in md
        assert "Hi there!" in md

    def test_session_without_session_id(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="codex", roots=(tmp_path,))
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(metadata={}, messages=[])
        md = markdown_for_session(source, session_file, session, digest="abc")

        # Should use path stem as fallback
        assert "test / session" in md

    def test_empty_messages(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "s.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(metadata={"session_id": "x"}, messages=[])
        md = markdown_for_session(source, session_file, session, digest="abc")

        assert "No transcript messages" in md

    def test_message_with_timestamp(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "s.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(
            metadata={},
            messages=[
                SessionMessage(role="user", text="Hi", timestamp="2026-01-01T00:00:00Z")
            ],
        )
        md = markdown_for_session(source, session_file, session, digest="abc")
        assert "(2026-01-01T00:00:00Z)" in md

    def test_metadata_keys_sorted(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "s.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(
            metadata={"z_key": "z", "a_key": "a", "m_key": "m"},
            messages=[],
        )
        md = markdown_for_session(source, session_file, session, digest="abc")
        # Check sorted order in output
        a_pos = md.index("- a_key:")
        m_pos = md.index("- m_key:")
        z_pos = md.index("- z_key:")
        assert a_pos < m_pos < z_pos

    def test_none_metadata_skipped(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "s.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(
            metadata={"keep": "value", "skip": None, "empty": ""},
            messages=[],
        )
        md = markdown_for_session(source, session_file, session, digest="abc")
        assert "- keep: `value`" in md
        assert "- skip:" not in md
        assert "- empty:" not in md

    def test_no_imported_at_uses_now(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "s.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(metadata={}, messages=[])
        md = markdown_for_session(source, session_file, session, digest="abc")
        assert "Imported at:" in md

    def test_message_role_fallback(self, tmp_path: Path) -> None:
        source = Source(name="test", kind="claude", roots=(tmp_path,))
        session_file = tmp_path / "s.jsonl"
        session_file.write_text("dummy", encoding="utf-8")
        session = ExtractedSession(
            metadata={},
            messages=[SessionMessage(role="", text="Anonymous message")],
        )
        md = markdown_for_session(source, session_file, session, digest="abc")
        assert "### 1. message" in md


class TestModifiedTimestamp:
    def test_returns_iso_format(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("hello", encoding="utf-8")
        result = modified_timestamp(path)
        # Should be parseable
        import datetime as dt

        parsed = dt.datetime.fromisoformat(result)
        assert parsed.tzinfo is not None


def _import_blocking_reportlab(exc: Exception) -> Callable[..., Any]:
    """Build an ``__import__`` replacement that fails only for reportlab.

    The real ``__import__`` is captured now, before any patch is installed, so
    the delegation below cannot recurse into the patched version. Everything
    other than reportlab must keep importing normally: CPython does lazy
    imports from inside the standard library (``pathlib.PurePath.__init__``
    imports ``ntpath`` on 3.12.3, for example), so a blanket failure breaks
    unrelated machinery rather than exercising ``write_pdf``.
    """

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "reportlab" or name.startswith("reportlab."):
            raise exc
        return real_import(name, *args, **kwargs)

    return fake_import


class TestWritePdf:
    def test_returns_false_when_reportlab_missing(self, tmp_path: Path) -> None:
        # Build the path before patching: constructing it under the patch would
        # route pathlib's own lazy imports through the mock.
        out_path = tmp_path / "test.pdf"
        fake_import = _import_blocking_reportlab(ImportError("No module named 'reportlab'"))

        with patch("builtins.__import__", side_effect=fake_import):
            result = write_pdf("# Test", out_path)

        assert result is False
        assert not out_path.exists()

    def test_returns_false_on_import_error(self, tmp_path: Path) -> None:
        # A non-ImportError must also be swallowed: render.py catches bare
        # Exception so a broken reportlab install degrades instead of crashing.
        out_path = tmp_path / "test.pdf"
        fake_import = _import_blocking_reportlab(RuntimeError("reportlab not available"))

        with patch("builtins.__import__", side_effect=fake_import):
            result = write_pdf("# Test", out_path)

        assert result is False
        assert not out_path.exists()

    def test_import_helper_delegates_other_modules(self) -> None:
        # Guards the regression this row fixes: the helper must not block
        # unrelated imports, including the lazy stdlib ones.
        fake_import = _import_blocking_reportlab(ImportError("blocked"))

        with patch("builtins.__import__", side_effect=fake_import):
            import ntpath as patched_ntpath

            assert patched_ntpath is not None

    def test_writes_pdf_when_reportlab_available(self, tmp_path: Path) -> None:
        """Integration-style test that actually writes a PDF if reportlab is installed."""
        import pytest

        try:
            from importlib.util import find_spec

            if not find_spec("reportlab"):
                pytest.skip("reportlab not installed")
        except ImportError:
            pytest.skip("reportlab not installed")

        out_path = tmp_path / "test.pdf"
        result = write_pdf("# Hello\n\nBody text here.", out_path)
        assert result is True
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_pdf_handles_multiple_headings(self, tmp_path: Path) -> None:
        import pytest

        try:
            from importlib.util import find_spec

            if not find_spec("reportlab"):
                pytest.skip("reportlab not installed")
        except ImportError:
            pytest.skip("reportlab not installed")

        out_path = tmp_path / "test.pdf"
        markdown = (
            "# Title\n\n## Section\n\n### Subsection\n\nContent.\n\nMore content."
        )
        result = write_pdf(markdown, out_path)
        assert result is True
