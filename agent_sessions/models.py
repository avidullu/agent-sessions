"""Shared archive data models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Source:
    name: str
    kind: str
    roots: tuple[Path, ...]
    glob: str = "**/*"
    description: str = ""


@dataclass(frozen=True)
class SessionMessage:
    role: str
    text: str
    timestamp: str = ""


@dataclass(frozen=True)
class ExtractedSession:
    metadata: dict[str, Any]
    messages: list[SessionMessage]
