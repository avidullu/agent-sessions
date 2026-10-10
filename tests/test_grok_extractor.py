"""Tests for agent_sessions.sources.grok extractor."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.archive import export_sources, read_existing_index_records
from agent_sessions.config import ArchiveConfig
from agent_sessions.models import Source
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
        assert result.unsupported_rows == 0

    def test_encrypted_content_without_text_is_unsupported(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join([
                json.dumps({"type": "user", "content": [{"text": "Hello"}], "timestamp": "2026-01-01T00:00:00Z"}),
                json.dumps({"type": "assistant", "content": None, "encrypted_content": "ciphertext-not-transcript"}),
                json.dumps({"message": {"role": "assistant", "encrypted_content": "nested-ciphertext"}}),
            ]) + "\n",
            encoding="utf-8",
        )
        result = extract(path)
        assert len(result.messages) == 1
        assert result.messages[0].text == "Hello"
        assert result.unsupported_rows == 2

    def test_tool_rows_without_text_are_unsupported(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join([
                json.dumps({
                    "type": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call-1", "function": {"name": "list_dir", "arguments": "{}"}}],
                }),
                json.dumps({"role": "tool", "content": None, "tool_calls": [{"id": "call-1"}]}),
                json.dumps({"type": "assistant", "content": [{"type": "tool_use", "id": "call-2"}]}),
                json.dumps({"message": {"role": "tool", "tool_calls": [{"id": "nested"}]}}),
            ]) + "\n",
            encoding="utf-8",
        )
        result = extract(path)
        assert result.messages == []
        assert result.unsupported_rows == 4

    def test_text_alongside_tools_or_ciphertext_stays_supported(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join([
                json.dumps({
                    "type": "assistant",
                    "content": [{"text": "Done."}],
                    "tool_calls": [{"id": "call-1"}],
                    "encrypted_content": "ciphertext",
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        result = extract(path)
        assert [message.text for message in result.messages] == ["Done."]
        assert result.unsupported_rows == 0

    def test_export_marks_dropped_rows_partial(self, tmp_path: Path) -> None:
        source = tmp_path / "project" / "session" / "chat_history.jsonl"
        source.parent.mkdir(parents=True)
        source.write_text(
            "\n".join([
                json.dumps({"type": "user", "content": "Keep this turn"}),
                json.dumps({"type": "assistant", "encrypted_content": "hidden", "content": None}),
            ]) + "\n",
            encoding="utf-8",
        )
        config = ArchiveConfig(
            tmp_path,
            tmp_path / "archive",
            tmp_path / "raw",
            (Source("grok-local", "grok", (source.parents[2],), "**/chat_history.jsonl"),),
        )
        result = export_sources(config)
        row = read_existing_index_records(config)[0]
        assert result.exported == 1
        assert result.unsupported_files == 1
        assert row["messages"] == 1
        assert row["unsupported_rows"] == 1
        assert row["parse_status"] == "partial"

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        result = extract(path)
        assert result.messages == []

    def test_metadata_row_is_not_an_unsupported_drop(self, tmp_path: Path) -> None:
        path = tmp_path / "p" / "s" / "chat_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"type": "metadata", "content": null}\n', encoding="utf-8")
        result = extract(path)
        assert result.messages == []
        assert result.metadata_records == 1
        assert result.unsupported_rows == 0
