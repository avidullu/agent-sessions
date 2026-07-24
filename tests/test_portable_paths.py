"""Tests for the portable-path convention used by tracked catalogs (L1)."""

from __future__ import annotations

from agent_sessions.portable_paths import (
    portable_metadata,
    portable_origin,
    portable_path,
    portable_record,
)


class TestPortablePath:
    def test_windows_home_backslashes(self) -> None:
        assert portable_path("C:\\Users\\alice\\.codex\\sessions\\x.jsonl") == "~\\.codex\\sessions\\x.jsonl"

    def test_windows_home_forward_slashes(self) -> None:
        assert portable_path("D:/Users/bob/.claude/projects/a.jsonl") == "~/.claude/projects/a.jsonl"

    def test_windows_home_exactly(self) -> None:
        assert portable_path("C:\\Users\\alice") == "~"

    def test_wsl_unc_home(self) -> None:
        assert portable_path("\\\\wsl.localhost\\Ubuntu\\home\\alice\\y.jsonl") == "~\\y.jsonl"

    def test_wsl_dollar_home(self) -> None:
        assert portable_path("//wsl$/Debian/home/alice/y.jsonl") == "~/y.jsonl"

    def test_posix_home(self) -> None:
        assert portable_path("/home/alice/.claude/projects/a.jsonl") == "~/.claude/projects/a.jsonl"

    def test_mounted_windows_home(self) -> None:
        assert portable_path("/mnt/c/Users/alice/z.md") == "~/z.md"

    def test_macos_home(self) -> None:
        assert portable_path("/Users/alice/Library/x.json") == "~/Library/x.json"

    def test_encoded_claude_project_key(self) -> None:
        assert (
            portable_path("C:\\Users\\alice\\.claude\\projects\\C--Users-alice-Projects-demo\\s.jsonl")
            == "~\\.claude\\projects\\~-Projects-demo\\s.jsonl"
        )

    def test_encoded_key_in_placeholdered_path(self) -> None:
        assert (
            portable_path("<claude-projects>/C--Users-bob-Projects-app/x.jsonl")
            == "<claude-projects>/~-Projects-app/x.jsonl"
        )

    def test_encoded_posix_key(self) -> None:
        assert portable_path("<claude-projects>/-home-bob-repos-app/x.jsonl") == "<claude-projects>/~-repos-app/x.jsonl"

    def test_idempotent(self) -> None:
        once = portable_path("C:\\Users\\alice\\.codex\\sessions\\x.jsonl")
        assert portable_path(once) == once

    def test_non_path_text_unchanged(self) -> None:
        assert portable_path("no home prefix here") == "no home prefix here"

    def test_encoded_segment_needs_path_context(self) -> None:
        # Free text without separators is left alone even if it superficially
        # resembles an encoded segment mid-string.
        assert portable_path("try -home-brew tastes fine") == "try -home-brew tastes fine"

    def test_bare_encoded_project_key(self) -> None:
        # Metadata values like "project" hold the encoded key on its own, with
        # no separators; the leading encoded prefix is enough path context.
        assert portable_path("C--Users-alice-Projects-app") == "~-Projects-app"
        assert portable_path("-home-alice-repos-app") == "~-repos-app"

    def test_non_home_absolute_path_unchanged(self) -> None:
        assert portable_path("C:\\ProgramData\\app\\log.txt") == "C:\\ProgramData\\app\\log.txt"


class TestPortableOrigin:
    def test_windows(self) -> None:
        assert portable_origin("C:\\Users\\alice\\.codex\\x.jsonl") == "windows-user:C"

    def test_windows_forward_slashes(self) -> None:
        assert portable_origin("c:/Users/alice/.codex/x.jsonl") == "windows-user:C"

    def test_wsl(self) -> None:
        assert portable_origin("\\\\wsl.localhost\\Ubuntu\\home\\alice\\x") == "wsl-user:Ubuntu"

    def test_posix(self) -> None:
        assert portable_origin("/home/alice/x.jsonl") == "posix-home"

    def test_macos(self) -> None:
        assert portable_origin("/Users/alice/x.jsonl") == "macos-user"

    def test_mounted_windows(self) -> None:
        assert portable_origin("/mnt/c/Users/alice/x.jsonl") == "wsl-mounted-windows-user:C"

    def test_already_portable_is_unknown(self) -> None:
        assert portable_origin("~/x.jsonl") == "unknown"


class TestPortableMetadata:
    def test_nested_values_normalized(self) -> None:
        metadata = {
            "cwd": "C:\\Users\\alice\\Projects\\demo",
            "nested": {"paths": ["/home/alice/a", 7, None]},
            "title": "plain text",
        }
        assert portable_metadata(metadata) == {
            "cwd": "~\\Projects\\demo",
            "nested": {"paths": ["~/a", 7, None]},
            "title": "plain text",
        }


class TestPortableRecord:
    def test_backfills_origin_and_normalizes(self) -> None:
        record = {
            "source": "codex-windows",
            "source_file": "C:\\Users\\alice\\.codex\\sessions\\x.jsonl",
            "metadata": {"cwd": "C:\\Users\\alice\\Projects\\demo"},
        }
        upgraded = portable_record(record)
        assert upgraded["source_file"] == "~\\.codex\\sessions\\x.jsonl"
        assert upgraded["source_origin"] == "windows-user:C"
        assert upgraded["metadata"]["cwd"] == "~\\Projects\\demo"
        # The input record is not mutated.
        assert str(record["source_file"]).startswith("C:")

    def test_existing_origin_preserved(self) -> None:
        record = {"source_file": "/home/alice/x", "source_origin": "posix-home"}
        assert portable_record(record)["source_origin"] == "posix-home"

    def test_portable_record_is_stable_when_already_portable(self) -> None:
        record = {"source": "s", "source_file": "~/x.jsonl", "source_origin": "posix-home"}
        assert portable_record(record) == record
