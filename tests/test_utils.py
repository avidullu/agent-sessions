"""Tests for agent_sessions.utils."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from agent_sessions.utils import (
    archive_markdown_path,
    canonical_agent,
    jsonl_objects,
    now_utc,
    read_jsonl_dicts,
    session_id_from_name,
    slugify,
    text_from_content,
)


class TestCanonicalAgent:
    def test_native_vscode_provider_distinguishes_zai(self) -> None:
        assert (
            canonical_agent(
                {
                    "kind": "copilot_chat",
                    "source": "zai-vscode",
                    "metadata": {"model_provider": "zai"},
                }
            )
            == "zai"
        )

    def test_native_vscode_provider_defaults_to_copilot(self) -> None:
        assert canonical_agent({"kind": "copilot_chat", "source": "copilot-vscode"}) == "copilot"

    def test_native_vscode_github_providers_map_to_copilot(self) -> None:
        for provider in ("github", "github-copilot"):
            assert (
                canonical_agent(
                    {
                        "kind": "copilot_chat",
                        "source": "copilot-vscode",
                        "metadata": {"model_provider": provider},
                    }
                )
                == "copilot"
            )


class TestReadJsonlDicts:
    def test_skips_malformed_line_with_warning(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "data.jsonl"
        path.write_text('{"a": 1}\nnot json\n{"b": 2}\n', encoding="utf-8")
        records = read_jsonl_dicts(path, label="data.jsonl")
        assert records == [{"a": 1}, {"b": 2}]
        assert "skipping malformed JSON at data.jsonl:2" in capsys.readouterr().err

    def test_ignores_non_dict_json(self, tmp_path: Path) -> None:
        path = tmp_path / "data.jsonl"
        path.write_text('{"a": 1}\n[1, 2, 3]\n', encoding="utf-8")
        assert read_jsonl_dicts(path) == [{"a": 1}]


class TestNowUtc:
    def test_returns_isoformat(self) -> None:
        result = now_utc()
        # Should be parseable as ISO datetime
        parsed = dt.datetime.fromisoformat(result)
        assert parsed.tzinfo is not None
        assert parsed.tzinfo == dt.UTC

    def test_has_seconds_precision(self) -> None:
        result = now_utc()
        # Format like 2026-07-06T12:34:56+00:00
        assert "T" in result
        assert "+" in result or result.endswith("Z")
        # No microseconds
        assert "." not in result

    def test_is_current(self) -> None:
        result = now_utc()
        parsed = dt.datetime.fromisoformat(result)
        now = dt.datetime.now(dt.UTC)
        diff = abs((now - parsed).total_seconds())
        assert diff < 5  # within 5 seconds


class TestJsonlObjects:
    def test_basic(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        path.write_text(
            '{"a": 1}\n{"b": 2}\n',
            encoding="utf-8",
        )
        results = list(jsonl_objects(path))
        assert results == [{"a": 1}, {"b": 2}]

    def test_skips_empty_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        path.write_text(
            '\n{"a": 1}\n\n{"b": 2}\n\n',
            encoding="utf-8",
        )
        results = list(jsonl_objects(path))
        assert results == [{"a": 1}, {"b": 2}]

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        path.write_text(
            '{"a": 1}\nnot-json\n{"b": 2}\n',
            encoding="utf-8",
        )
        results = list(jsonl_objects(path))
        assert results == [{"a": 1}, {"b": 2}]

    def test_skips_non_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        path.write_text(
            '{"a": 1}\n["list"]\n42\n{"b": 2}\n',
            encoding="utf-8",
        )
        results = list(jsonl_objects(path))
        assert results == [{"a": 1}, {"b": 2}]

    def test_handles_encoding_errors(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        # Write raw bytes that include invalid UTF-8
        path.write_bytes(b'{"a": 1}\n{"b": \xff}\n{"c": 2}\n')
        results = list(jsonl_objects(path))
        # The invalid line should be skipped, valid ones retained
        assert len(results) >= 1

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        path.write_text("", encoding="utf-8")
        results = list(jsonl_objects(path))
        assert results == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.jsonl"
        with pytest.raises(FileNotFoundError):
            list(jsonl_objects(path))


class TestTextFromContent:
    def test_none(self) -> None:
        assert text_from_content(None) == ""

    def test_string(self) -> None:
        assert text_from_content("hello") == "hello"

    def test_empty_string(self) -> None:
        assert text_from_content("") == ""

    def test_list_of_strings(self) -> None:
        result = text_from_content(["a", "b", "c"])
        assert result == "a\nb\nc"

    def test_list_of_dicts_with_text(self) -> None:
        result = text_from_content([{"text": "hello"}, {"text": "world"}])
        assert result == "hello\nworld"

    def test_list_of_dicts_with_content(self) -> None:
        result = text_from_content([{"content": "hello"}, {"content": "world"}])
        assert result == "hello\nworld"

    def test_list_of_dicts_with_input(self) -> None:
        result = text_from_content([{"input": "hello"}])
        assert result == "hello"

    def test_nested_content(self) -> None:
        result = text_from_content([{"content": [{"text": "nested"}]}])
        assert result == "nested"

    def test_dict_with_text_key(self) -> None:
        assert text_from_content({"text": "hello"}) == "hello"

    def test_dict_with_content_key(self) -> None:
        assert text_from_content({"content": "world"}) == "world"

    def test_dict_with_message_key(self) -> None:
        assert text_from_content({"message": "hi"}) == "hi"

    def test_dict_with_input_key(self) -> None:
        assert text_from_content({"input": "test"}) == "test"

    def test_dict_with_output_key(self) -> None:
        assert text_from_content({"output": "result"}) == "result"

    def test_dict_without_known_keys(self) -> None:
        assert text_from_content({"unknown": "value"}) == ""

    def test_mixed_list(self) -> None:
        result = text_from_content(["a", {"text": "b"}, "c", {"content": "d"}])
        assert result == "a\nb\nc\nd"

    def test_nested_dict_list(self) -> None:
        result = text_from_content({"text": [{"text": "deep"}]})
        assert result == "deep"

    def test_list_with_empty_items(self) -> None:
        result = text_from_content(["a", "", None, "b"])
        # Empty strings are included due to truthiness check being part of join
        assert "a" in result
        assert "b" in result


class TestSessionIdFromName:
    def test_uuid_in_name(self) -> None:
        path = Path(
            "20260530-aa329f09-28b7-4acc-b062-98ec7e905abc-agent-something.jsonl"
        )
        result = session_id_from_name(path)
        assert result == "aa329f09-28b7-4acc-b062-98ec7e905abc"

    def test_no_uuid_falls_back_to_stem(self) -> None:
        path = Path("simple-session.jsonl")
        result = session_id_from_name(path)
        assert result == "simple-session"

    def test_multiple_uuids_returns_first(self) -> None:
        path = Path(
            "abc12345-1234-4234-8234-123456789abc-xyz-def12345-5678-4678-9678-abcdef123456.jsonl"
        )
        result = session_id_from_name(path)
        assert result == "abc12345-1234-4234-8234-123456789abc"

    def test_case_insensitive_uuid(self) -> None:
        path = Path("AA329F09-28B7-4ACC-B062-98EC7E905ABC-agent.jsonl")
        result = session_id_from_name(path)
        assert result == "AA329F09-28B7-4ACC-B062-98EC7E905ABC"


class TestArchiveMarkdownPath:
    def test_forward_slashes(self, repo_root: Path) -> None:
        result = archive_markdown_path(repo_root, "archive/claude/session.md")
        assert result == repo_root / "archive" / "claude" / "session.md"

    def test_windows_backslashes(self, repo_root: Path) -> None:
        result = archive_markdown_path(repo_root, "archive\\claude\\session.md")
        assert result == repo_root / "archive" / "claude" / "session.md"

    def test_mixed_separators(self, repo_root: Path) -> None:
        result = archive_markdown_path(repo_root, "archive/claude\\session.md")
        assert result == repo_root / "archive" / "claude" / "session.md"


class TestSlugify:
    def test_simple(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_special_characters(self) -> None:
        result = slugify("foo!@#bar")
        assert result.startswith("foo")
        assert result.endswith("bar")
        assert "foo" in result
        assert "bar" in result

    def test_leading_trailing_special(self) -> None:
        assert slugify("--hello--") == "hello"

    def test_spaces_and_underscores(self) -> None:
        assert slugify("  my  session  name  ") == "my-session-name"

    def test_max_length(self) -> None:
        long_name = "a" * 100
        result = slugify(long_name, max_len=50)
        assert len(result) <= 50

    def test_empty_becomes_session(self) -> None:
        assert slugify("!!!") == "session"

    def test_dots_and_hyphens_preserved(self) -> None:
        assert slugify("v1.2.3-beta") == "v1.2.3-beta"

    def test_mixed_unicode(self) -> None:
        result = slugify("résumé")
        # Non-ASCII chars become hyphens
        assert "r" in result
