"""Configuration loading for archive sources and paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from .models import Source
from .path_templates import PathTemplateContext


DEFAULT_CONFIG = Path("config/default_sources.toml")


@dataclass(frozen=True)
class ArchiveConfig:
    repo_root: Path
    archive_dir: Path
    raw_dir: Path
    sources: tuple[Source, ...]


def load_config(repo_root: Path, config_path: Path | None = None) -> ArchiveConfig:
    path = config_path or repo_root / "sources.toml"
    if not path.exists():
        path = repo_root / DEFAULT_CONFIG
    data = read_toml(path)
    templates = PathTemplateContext.from_environment(repo_root)
    archive_settings = data.get("archive", {})
    archive_dir = repo_path(repo_root, archive_settings.get("archive_dir", "archive"))
    raw_dir = repo_path(repo_root, archive_settings.get("raw_dir", "raw"))
    sources = tuple(load_source(item, templates) for item in data.get("sources", []) if item.get("enabled", True))
    return ArchiveConfig(repo_root=repo_root, archive_dir=archive_dir, raw_dir=raw_dir, sources=sources)


def read_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        raise SystemExit("Python 3.11+ is required to read TOML config.")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_source(item: dict[str, Any], templates: PathTemplateContext) -> Source:
    return Source(
        name=item["name"],
        kind=item["kind"],
        roots=tuple(templates.resolve(root) for root in item.get("roots", [])),
        glob=item.get("glob", "**/*"),
        description=item.get("description", ""),
    )


def repo_path(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return repo_root / path
