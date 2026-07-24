"""Claude Code session extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ExtractedSession, SessionMessage
from ..utils import jsonl_objects, text_from_content
from .registry import register


@register("claude")
def extract(path: Path) -> ExtractedSession:
    metadata: dict[str, Any] = {"session_id": path.stem, "project": path.parent.name}
    messages: list[SessionMessage] = []
    for obj in jsonl_objects(path):
        if obj.get("sessionId"):
            metadata["session_id"] = obj.get("sessionId")
        message = obj.get("message")
        if isinstance(message, dict):
            role = message.get("role") or obj.get("type") or "message"
            content = text_from_content(message.get("content"))
            if content:
                messages.append(SessionMessage(role=role, text=content, timestamp=obj.get("timestamp", "")))
            continue
        if obj.get("type") == "summary" and obj.get("content"):
            messages.append(
                SessionMessage(role="summary", text=text_from_content(obj.get("content")), timestamp=obj.get("timestamp", ""))
            )
    return ExtractedSession(metadata=metadata, messages=messages)
