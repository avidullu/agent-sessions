"""Tests for agent_sessions.sources.claude extractor."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.sources.claude import extract


class TestClaudeExtract:
    def test_basic_extraction(self, tmp_path: Path, sample_claude_jsonl: str) -> None:
        path = tmp_path / "session.jsonl"
        path.write_text(sample_claude_jsonl, encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "abc-123"
        assert result.metadata["project"] == path.parent.name  # parent dir name

        # Should have 4 messages: user, assistant, summary, tool
        assert len(result.messages) == 4
        roles = [m.role for m in result.messages]
        assert "user" in roles
        assert "assistant" in roles
        assert "summary" in roles

        # Check user message content
        user_msg = next(m for m in result.messages if m.role == "user")
        assert "Hello, Claude!" in user_msg.text

    def test_summary_extraction(self, tmp_path: Path) -> None:
        line = json.dumps(
            {
                "sessionId": "s1",
                "type": "summary",
                "content": "Summary text here.",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        path = tmp_path / "session.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 1
        assert result.messages[0].role == "summary"
        assert result.messages[0].text == "Summary text here."

    def test_empty_message_skipped(self, tmp_path: Path) -> None:
        line = json.dumps(
            {"sessionId": "s1", "message": {"role": "user", "content": [{"text": ""}]}}
        )
        path = tmp_path / "session.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 0

    def test_no_session_id_uses_stem(self, tmp_path: Path) -> None:
        line = json.dumps({"message": {"role": "user", "content": [{"text": "Hi"}]}})
        path = tmp_path / "my-session.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "my-session"

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        result = extract(path)
        assert result.messages == []

    def test_type_as_role_fallback(self, tmp_path: Path) -> None:
        """When message has no role, use the top-level type as role."""
        line = json.dumps(
            {
                "sessionId": "s1",
                "type": "tool_use",
                "message": {"content": [{"text": "Tool output."}]},
            }
        )
        path = tmp_path / "session.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) >= 1
        assert result.messages[0].text == "Tool output."

    def test_tool_message_with_role(self, tmp_path: Path) -> None:
        line = json.dumps(
            {"sessionId": "s1", "message": {"role": "tool", "content": "Tool result."}}
        )
        path = tmp_path / "session.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 1
        assert result.messages[0].role == "tool"
        assert result.messages[0].text == "Tool result."
