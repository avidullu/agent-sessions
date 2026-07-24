"""Extractor registry keyed by source kind."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..models import ExtractedSession

Extractor = Callable[[Path], ExtractedSession]

_EXTRACTORS: dict[str, Extractor] = {}


def register(kind: str) -> Callable[[Extractor], Extractor]:
    def decorator(extractor: Extractor) -> Extractor:
        _EXTRACTORS[kind] = extractor
        return extractor

    return decorator


def get_extractor(kind: str) -> Extractor | None:
    import agent_sessions.sources  # noqa: F401

    return _EXTRACTORS.get(kind)


def known_kinds() -> tuple[str, ...]:
    import agent_sessions.sources  # noqa: F401

    return tuple(sorted(_EXTRACTORS))
