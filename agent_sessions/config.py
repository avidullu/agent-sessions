"""Configuration loading for archive sources and paths."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Source
from .path_templates import PathTemplateContext

DEFAULT_CONFIG = Path("config/default_sources.toml")


@dataclass(frozen=True)
class ArchiveConfig:
    repo_root: Path
    archive_dir: Path
    raw_dir: Path
    sources: tuple[Source, ...]
    write_pdfs: bool = False
    track_artifacts: bool = False
    disabled_sources: tuple[Source, ...] = ()
    backup_dir: Path | None = None
    backup_machine: str | None = None
    backup_on_export: bool = False


def load_config(repo_root: Path, config_path: Path | None = None) -> ArchiveConfig:
    path = repo_path(repo_root, str(config_path)) if config_path is not None else repo_root / "sources.toml"
    if config_path is None and not path.exists():
        path = repo_root / DEFAULT_CONFIG
    if not path.exists():
        raise SystemExit(
            f"Configuration not found: {path}. Run agent-archive --repo-root \"{repo_root}\" init "
            "or pass --config with an existing sources TOML file."
        )
    data = read_toml(path)
    templates = PathTemplateContext.from_environment(repo_root)
    archive_settings = data.get("archive", {})
    if not isinstance(archive_settings, dict):
        raise ValueError("Archive settings must be a TOML table.")
    archive_dir = repo_path(repo_root, config_string(archive_settings, "archive_dir", "archive", "archive"))
    raw_dir = repo_path(repo_root, config_string(archive_settings, "raw_dir", "raw", "archive"))
    write_pdfs = config_boolean(archive_settings, "write_pdfs", False, "archive")
    track_artifacts = config_boolean(archive_settings, "track_artifacts", False, "archive")
    source_settings = data.get("sources", [])
    if not isinstance(source_settings, list):
        raise ValueError("Sources settings must be an array of TOML tables ([[sources]]).")
    enabled_sources: list[Source] = []
    disabled_sources: list[Source] = []
    for number, item in enumerate(source_settings, 1):
        if not isinstance(item, dict):
            raise ValueError(f"sources[{number}] must be a TOML table.")
        enabled = config_boolean(item, "enabled", True, f"sources[{number}]")
        source = load_source(item, templates)
        (enabled_sources if enabled else disabled_sources).append(source)
    backup_settings = data.get("backup", {})
    if not isinstance(backup_settings, dict):
        raise ValueError("Backup settings must be a TOML table.")
    backup_on_export = config_boolean(backup_settings, "on_export", False, "backup")
    backup_machine = backup_settings.get("machine")
    if backup_machine is not None:
        backup_machine = config_string(backup_settings, "machine", "", "backup")
    backup_directory = backup_settings.get("directory")
    backup_dir = None
    if backup_directory is not None:
        if not isinstance(backup_directory, str) or not backup_directory.strip():
            raise ValueError("Backup directory must be a nonempty path string.")
        try:
            backup_dir = repo_path(repo_root, str(templates.resolve(backup_directory)))
        except (SystemExit, ValueError, AttributeError) as exc:
            raise ValueError("Invalid backup directory template.") from exc
    return ArchiveConfig(
        repo_root=repo_root,
        archive_dir=archive_dir,
        raw_dir=raw_dir,
        sources=tuple(enabled_sources),
        backup_dir=backup_dir,
        backup_machine=backup_machine,
        backup_on_export=backup_on_export,
        write_pdfs=write_pdfs,
        track_artifacts=track_artifacts,
        disabled_sources=tuple(disabled_sources),
    )


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_source(item: dict[str, Any], templates: PathTemplateContext) -> Source:
    for required in ("name", "kind"):
        if required not in item:
            raise SystemExit(f"Invalid source entry in config: missing required key {required!r}. Entry: {item!r}")
    name = config_string(item, "name", "", "source")
    kind = config_string(item, "kind", "", f"source {name!r}")
    roots = item.get("roots", [])
    if not isinstance(roots, list) or not all(isinstance(root, str) and root.strip() for root in roots):
        raise ValueError(f"source {name!r}.roots must be an array of nonempty path strings.")
    description = item.get("description", "")
    if not isinstance(description, str):
        raise ValueError(f"source {name!r}.description must be a string.")
    return Source(name=name, kind=kind, roots=tuple(templates.resolve(root) for root in roots),
                  glob=config_string(item, "glob", "**/*", f"source {name!r}"), description=description)


def config_boolean(settings: dict[str, Any], key: str, default: bool, section: str) -> bool:
    value = settings.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{section}.{key} must be a TOML boolean (true or false, without quotes).")
    return value


def config_string(settings: dict[str, Any], key: str, default: str, section: str) -> str:
    value = settings.get(key, default)
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{section}.{key} must be a nonempty string.")
    return value


def repo_path(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return repo_root / path
