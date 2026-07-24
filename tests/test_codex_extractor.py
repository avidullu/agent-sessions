"""Tests for agent_sessions.sources.codex extractor."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.sources.codex import extract


class TestCodexExtract:
    def test_basic_extraction(self, tmp_path: Path, sample_codex_jsonl: str) -> None:
        path = tmp_path / "codex-session.jsonl"
        path.write_text(sample_codex_jsonl, encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "codex-456"
        assert result.metadata["cwd"] == "/home/user/project"
        assert result.metadata["model_provider"] == "openai"
        assert result.metadata["cli_version"] == "1.0.0"
        assert result.metadata["source"] == "codex"

        # Should have 2 messages: user and assistant
        assert len(result.messages) == 2
        roles = [m.role for m in result.messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_session_id_from_name_fallback(self, tmp_path: Path) -> None:
        """When no session_meta line, session_id falls back to UUID from filename."""
        path = tmp_path / "20260101-aa329f09-28b7-4acc-b062-98ec7e905abc-agent.jsonl"
        line = json.dumps(
            {
                "type": "message",
                "payload": {"role": "user", "content": [{"text": "Hi"}]},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "aa329f09-28b7-4acc-b062-98ec7e905abc"

    def test_session_meta_updates_id(self, tmp_path: Path) -> None:
        path = tmp_path / "codex-session.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "message",
                    "payload": {"role": "user", "content": [{"text": "Hi"}]},
                }
            ),
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {"session_id": "updated-id", "cwd": "/tmp"},
                }
            ),
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "updated-id"

    def test_id_fallback_in_session_meta(self, tmp_path: Path) -> None:
        """session_meta may use 'id' instead of 'session_id'."""
        path = tmp_path / "codex-session.jsonl"
        line = json.dumps({"type": "session_meta", "payload": {"id": "fallback-id"}})
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "fallback-id"

    def test_skips_non_dict_payload(self, tmp_path: Path) -> None:
        path = tmp_path / "codex-session.jsonl"
        line = json.dumps({"type": "session_meta", "payload": "not-a-dict"})
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        # Should not crash; session_id from filename
        assert "session_id" in result.metadata

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        result = extract(path)
        assert result.messages == []

    def test_message_without_role_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "codex-session.jsonl"
        line = json.dumps(
            {"type": "message", "payload": {"content": [{"text": "No role."}]}}
        )
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 0

    def test_message_with_string_content(self, tmp_path: Path) -> None:
        path = tmp_path / "codex-session.jsonl"
        line = json.dumps(
            {"type": "message", "payload": {"role": "user", "content": "Plain text."}}
        )
        path.write_text(line + "\n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 1
        assert result.messages[0].text == "Plain text."
