"""Grok local session extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ExtractedSession, SessionMessage
from ..utils import jsonl_objects, text_from_content
from .registry import register


@register("grok")
def extract(path: Path) -> ExtractedSession:
    metadata: dict[str, Any] = {"session_id": path.parent.name, "project": path.parent.parent.name}
    messages: list[SessionMessage] = []
    for obj in jsonl_objects(path):
        content = text_from_content(obj.get("content"))
        if not content:
            continue
        role = obj.get("type") or "message"
        messages.append(SessionMessage(role=role, text=content, timestamp=obj.get("timestamp", "")))
    return ExtractedSession(metadata=metadata, messages=messages)
