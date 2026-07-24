"""Tests for agent_sessions.sources.deepseek extractor."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.sources.deepseek import extract


class TestDeepseekExtract:
    def test_basic_extraction(self, tmp_path: Path, sample_deepseek_text: str) -> None:
        path = tmp_path / "request-dumps" / "msg1.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sample_deepseek_text, encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "request-dumps"
        assert result.metadata["request_file"] == "msg1.txt"
        assert len(result.messages) == 1
        assert result.messages[0].role == "request-prompt"
        assert "deepseek-v4" in result.messages[0].text

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "dumps" / "empty.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 0

    def test_whitespace_only_file(self, tmp_path: Path) -> None:
        path = tmp_path / "dumps" / "whitespace.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("   \n  \t  \n", encoding="utf-8")

        result = extract(path)
        assert len(result.messages) == 0

    def test_session_id_from_parent(self, tmp_path: Path) -> None:
        path = tmp_path / "my-session-id" / "msg.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("hello", encoding="utf-8")

        result = extract(path)
        assert result.metadata["session_id"] == "my-session-id"
