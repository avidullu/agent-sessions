"""Tests for agent_sessions.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_sessions.config import (
    ArchiveConfig,
    load_config,
    load_source,
    read_toml,
    repo_path,
)
from agent_sessions.models import Source
from agent_sessions.path_templates import PathTemplateContext


class TestRepoPath:
    def test_relative_path(self, tmp_path: Path) -> None:
        result = repo_path(tmp_path, "subdir/file.txt")
        assert result == tmp_path / "subdir" / "file.txt"

    def test_absolute_path(self, tmp_path: Path) -> None:
        abs_path = str(tmp_path / "absolute" / "file.txt")
        result = repo_path(tmp_path, abs_path)
        assert result == Path(abs_path)

    def test_empty_string(self, tmp_path: Path) -> None:
        result = repo_path(tmp_path, "")
        assert result == tmp_path


class TestLoadSource:
    def test_basic(self) -> None:
        templates = PathTemplateContext.from_environment(Path("/fake"))
        item = {"name": "test", "kind": "claude", "roots": ["/tmp/sessions"]}
        source = load_source(item, templates)
        assert source.name == "test"
        assert source.kind == "claude"
        assert source.glob == "**/*"
        assert source.description == ""

    def test_missing_required_key_raises_friendly_error(self) -> None:
        templates = PathTemplateContext.from_environment(Path("/fake"))
        with pytest.raises(SystemExit, match="missing required key 'kind'"):
            load_source({"name": "test", "roots": []}, templates)

    def test_with_custom_glob_and_description(self) -> None:
        templates = PathTemplateContext.from_environment(Path("/fake"))
        item = {
            "name": "test",
            "kind": "codex",
            "roots": ["/tmp"],
            "glob": "*.jsonl",
            "description": "desc",
        }
        source = load_source(item, templates)
        assert source.glob == "*.jsonl"
        assert source.description == "desc"

    def test_multiple_roots(self) -> None:
        templates = PathTemplateContext.from_environment(Path("/fake"))
        item = {"name": "test", "kind": "claude", "roots": ["/a", "/b"]}
        source = load_source(item, templates)
        assert len(source.roots) == 2

    def test_template_expansion(self, repo_root: Path) -> None:
        templates = PathTemplateContext.from_environment(repo_root)
        item = {
            "name": "test",
            "kind": "claude",
            "roots": ["{home}/.claude/projects"],
        }
        source = load_source(item, templates)
        assert len(source.roots) == 1
        # Normalize path separators for cross-platform compatibility
        normalized = str(source.roots[0]).replace("\\", "/")
        assert normalized.endswith(".claude/projects")


class TestReadToml:
    def test_reads_valid_toml(self, tmp_path: Path) -> None:
        path = tmp_path / "test.toml"
        path.write_text('[section]\nkey = "value"\n', encoding="utf-8")
        result = read_toml(path)
        assert result == {"section": {"key": "value"}}



class TestLoadConfig:
    def test_loads_from_sources_toml(
        self, repo_root: Path, minimal_sources_toml: Path
    ) -> None:
        config = load_config(repo_root, minimal_sources_toml)
        assert isinstance(config, ArchiveConfig)
        assert config.repo_root == repo_root
        assert len(config.sources) >= 1

    def test_falls_back_to_default_config(self, repo_root: Path) -> None:
        """When sources.toml is missing, fall back to config/default_sources.toml."""
        # Create the default config
        default_path = repo_root / "config" / "default_sources.toml"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        default_path.write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n\n'
            '[[sources]]\nname = "default-test"\nkind = "codex"\n'
            'roots = ["{home}/.codex/sessions"]\nglob = "**/*.jsonl"\n',
            encoding="utf-8",
        )
        config = load_config(repo_root)
        assert isinstance(config, ArchiveConfig)

    def test_archive_settings(
        self, repo_root: Path, minimal_sources_toml: Path
    ) -> None:
        config = load_config(repo_root, minimal_sources_toml)
        assert config.archive_dir.name == "archive"
        assert config.raw_dir.name == "raw"
        assert config.write_pdfs is False

    def test_archive_pdf_setting(self, repo_root: Path) -> None:
        path = repo_root / "sources.toml"
        path.write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\nwrite_pdfs = true\n\n'
            '[[sources]]\nname = "test-claude"\nkind = "claude"\n'
            'roots = ["{home}/.claude/projects"]\nglob = "**/*.jsonl"\n',
            encoding="utf-8",
        )

        config = load_config(repo_root, path)

        assert config.write_pdfs is True


class TestArchiveConfig:
    def test_frozen(self, repo_root: Path) -> None:
        sources = (Source(name="t", kind="k", roots=(Path("/tmp"),)),)
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=sources,
        )
        assert config.repo_root == repo_root
        assert config.sources == sources
        assert config.write_pdfs is False
