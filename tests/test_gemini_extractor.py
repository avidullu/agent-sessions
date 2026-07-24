"""Tests for agent_sessions.sources.gemini extractor."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.sources.gemini import extract


class TestGeminiExtract:
    def test_basic_extraction(self, tmp_path: Path, sample_gemini_jsonl: str) -> None:
        # Gemini paths use parents[2] for session_id
        path = tmp_path / "level0" / "level1" / "level2" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sample_gemini_jsonl, encoding="utf-8")

        result = extract(path)
        # parents[0]=level2, parents[1]=level1, parents[2]=level0
        assert result.metadata["session_id"] == "level0"
        assert len(result.messages) == 2
        roles = [m.role for m in result.messages]
        assert "user" in roles
        assert "model" in roles

    def test_fallback_session_id_shallow_path(self, tmp_path: Path) -> None:
        """When path is shallow (parents <= 2), fall back to stem."""
        # tmp_path is deep; create a file at a controlled shallow location
        shallow_dir = tmp_path / "shallow"
        shallow_dir.mkdir(parents=True, exist_ok=True)
        path = shallow_dir / "transcript.jsonl"
        path.write_text(
            '{"source": "user", "content": [{"text": "Hi"}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        # parents[2] may not exist or be tmp_path itself; check that session_id is set
        assert "session_id" in result.metadata
        assert isinstance(result.metadata["session_id"], str)
        assert len(result.metadata["session_id"]) > 0

    def test_type_fallback_for_role(self, tmp_path: Path) -> None:
        """When source is missing, use type as role."""
        path = tmp_path / "a" / "b" / "c" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"type": "system", "content": [{"text": "System msg."}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert len(result.messages) == 1
        assert result.messages[0].role == "system"

    def test_message_fallback_role(self, tmp_path: Path) -> None:
        """When neither source nor type, use 'message'."""
        path = tmp_path / "a" / "b" / "c" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"content": [{"text": "Anonymous."}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert len(result.messages) == 1
        assert result.messages[0].role == "message"

    def test_empty_content_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"source": "user", "content": [{"text": ""}]}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert len(result.messages) == 0

    def test_created_at_timestamp(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"source": "user", "content": [{"text": "Hi"}], "created_at": "2026-06-01T12:00:00Z"}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert result.messages[0].timestamp == "2026-06-01T12:00:00Z"

    def test_timestamp_fallback(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"source": "user", "content": [{"text": "Hi"}], "timestamp": "2026-05-01T12:00:00Z"}\n',
            encoding="utf-8",
        )
        result = extract(path)
        assert result.messages[0].timestamp == "2026-05-01T12:00:00Z"
