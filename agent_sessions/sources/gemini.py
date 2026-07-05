"""Gemini Antigravity transcript extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ExtractedSession, SessionMessage
from ..utils import jsonl_objects, text_from_content
from .registry import register


@register("gemini_antigravity")
def extract(path: Path) -> ExtractedSession:
    metadata: dict[str, Any] = {"session_id": path.parents[2].name if len(path.parents) > 2 else path.stem}
    messages: list[SessionMessage] = []
    for obj in jsonl_objects(path):
        content = text_from_content(obj.get("content"))
        if not content:
            continue
        role = obj.get("source") or obj.get("type") or "message"
        timestamp = obj.get("created_at") or obj.get("timestamp") or ""
        messages.append(SessionMessage(role=role, text=content, timestamp=timestamp))
    return ExtractedSession(metadata=metadata, messages=messages)
