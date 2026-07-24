"""Tests for agent_sessions.sources.grok extractor."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.sources.grok import extract


class TestGrokExtract:
    def test_basic_extraction(self, tmp_path: Path, sample_grok_jsonl: str) -> None:
        # Grok paths use parent for session_id and parent.parent for project
        path = tmp_path / "project-name" / "session-id" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sample_grok_jsonl, encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "session-id"
        assert result.metadata["project"] == "project-name"
        assert len(result.messages) == 2
        roles = [m.role for m in result.messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_type_fallback_role(self, tmp_path: Path) -> None:
        """When type is present but no known role, use type as role."""
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"type": "system", "content": [{"text": "System msg."}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert result.messages[0].role == "system"

    def test_message_fallback_role(self, tmp_path: Path) -> None:
        """When no type, use 'message'."""
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"content": [{"text": "Anonymous."}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert result.messages[0].role == "message"

    def test_empty_content_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"type": "user", "content": [{"text": ""}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert len(result.messages) == 0

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        result = extract(path)
        assert result.messages == []
