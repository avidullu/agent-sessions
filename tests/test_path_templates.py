"""Tests for agent_sessions.path_templates."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sessions.path_templates import (
    PathTemplateContext,
    _StrictTemplateValues,
    clean_wsl_output,
    discover_wsl_distro,
    discover_wsl_user,
    make_wsl_home,
    run_command,
)


class TestPathTemplateContext:
    def test_from_environment(self, repo_root: Path) -> None:
        ctx = PathTemplateContext.from_environment(repo_root)
        assert "repo_root" in ctx.values
        assert "home" in ctx.values
        assert "appdata" in ctx.values
        assert "localappdata" in ctx.values

    def test_resolve_home_template(self, repo_root: Path) -> None:
        ctx = PathTemplateContext.from_environment(repo_root)
        result = ctx.resolve("{home}/.claude/projects")
        assert result.parts[-2:] == (".claude", "projects")

    def test_resolve_repo_root_template(self, repo_root: Path) -> None:
        ctx = PathTemplateContext.from_environment(repo_root)
        result = ctx.resolve("{repo_root}/archive")
        assert result == repo_root / "archive"

    def test_resolve_missing_wsl_home(self, repo_root: Path) -> None:
        """When wsl_home is empty, path resolves to __missing_wsl_home__ fallback."""
        ctx = PathTemplateContext(
            values={"wsl_home": "", "wsl_vscode_server": "", "home": str(Path.home())}
        )
        result = ctx.resolve("{wsl_home}/.claude/projects")
        assert "__missing_wsl_home__" in str(result)

    def test_resolve_missing_wsl_vscode_server(self, repo_root: Path) -> None:
        ctx = PathTemplateContext(
            values={"wsl_home": "", "wsl_vscode_server": "", "home": str(Path.home())}
        )
        result = ctx.resolve("{wsl_vscode_server}/data")
        assert "__missing_wsl_vscode_server__" in str(result)

    def test_resolve_with_env_var(self, repo_root: Path) -> None:
        ctx = PathTemplateContext.from_environment(repo_root)
        # Test that $env vars are expanded
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = ctx.resolve("$TEST_VAR/path")
            assert result.name == "path"

    def test_resolve_unknown_template_raises(self, repo_root: Path) -> None:
        ctx = PathTemplateContext.from_environment(repo_root)
        with pytest.raises(SystemExit, match="Unknown path template variable"):
            ctx.resolve("{nonexistent_key}/path")

    def test_wsl_distro_from_env(self, repo_root: Path) -> None:
        with patch.dict(os.environ, {"AGENT_ARCHIVE_WSL_DISTRO": "Ubuntu-22.04"}):
            ctx = PathTemplateContext.from_environment(repo_root)
            assert ctx.values["wsl_distro"] == "Ubuntu-22.04"

    def test_wsl_user_from_env(self, repo_root: Path) -> None:
        with patch.dict(os.environ, {"AGENT_ARCHIVE_WSL_USER": "testuser"}):
            ctx = PathTemplateContext.from_environment(repo_root)
            assert ctx.values["wsl_user"] == "testuser"

    def test_appdata_from_env(self, repo_root: Path) -> None:
        with patch.dict(os.environ, {"APPDATA": "C:\\FakeAppData"}):
            ctx = PathTemplateContext.from_environment(repo_root)
            assert ctx.values["appdata"] == "C:\\FakeAppData"


class TestStrictTemplateValues:
    def test_missing_key_raises_keyerror(self) -> None:
        values = _StrictTemplateValues({"a": "1"})
        with pytest.raises(KeyError):
            _ = values["b"]

    def test_existing_key_works(self) -> None:
        values = _StrictTemplateValues({"a": "1"})
        assert values["a"] == "1"


class TestDiscoverWslDistro:
    def test_returns_first_non_empty_line(self) -> None:
        with patch(
            "agent_sessions.path_templates.run_command",
            return_value="\nUbuntu\n  \nDebian\n",
        ):
            result = discover_wsl_distro()
            assert result == "Ubuntu"

    def test_returns_empty_when_no_output(self) -> None:
        with patch("agent_sessions.path_templates.run_command", return_value=""):
            result = discover_wsl_distro()
            assert result == ""

    def test_returns_empty_on_all_blank_lines(self) -> None:
        with patch("agent_sessions.path_templates.run_command", return_value="\n  \n"):
            result = discover_wsl_distro()
            assert result == ""


class TestDiscoverWslUser:
    def test_returns_user_from_command(self) -> None:
        with patch(
            "agent_sessions.path_templates.run_command", return_value="testuser"
        ):
            result = discover_wsl_user("Ubuntu")
            assert result == "testuser"

    def test_empty_when_no_distro(self) -> None:
        result = discover_wsl_user("")
        assert result == ""

    def test_falls_back_to_username_env(self) -> None:
        with patch("agent_sessions.path_templates.run_command", return_value=""):
            with patch.dict(os.environ, {"USERNAME": "fallback_user"}):
                result = discover_wsl_user("Ubuntu")
                assert result == "fallback_user"


class TestMakeWslHome:
    def test_returns_path(self) -> None:
        result = make_wsl_home("Ubuntu", "testuser")
        assert "Ubuntu" in result
        assert "testuser" in result
        assert result.startswith("\\\\")

    def test_empty_when_no_distro(self) -> None:
        assert make_wsl_home("", "user") == ""

    def test_empty_when_no_user(self) -> None:
        assert make_wsl_home("Ubuntu", "") == ""


class TestRunCommand:
    def test_returns_stdout(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "output"
            result = run_command(["echo", "hello"])
            assert result == "output"

    def test_returns_empty_on_error(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = "error"
            result = run_command(["bad-command"])
            assert result == ""

    def test_returns_empty_on_file_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = run_command(["nonexistent"])
            assert result == ""

    def test_returns_empty_on_timeout(self) -> None:
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            result = run_command(["slow-command"])
            assert result == ""


class TestCleanWslOutput:
    def test_removes_null_bytes(self) -> None:
        assert clean_wsl_output("hel\x00lo") == "hello"

    def test_removes_carriage_returns(self) -> None:
        assert clean_wsl_output("hello\r\nworld") == "hello\nworld"

    def test_preserves_normal_text(self) -> None:
        assert clean_wsl_output("normal text") == "normal text"
