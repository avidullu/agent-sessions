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
    diagnostics: dict[str, int] = {}
    for obj in jsonl_objects(path, diagnostics=diagnostics):
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
        elif obj.get("sessionId") and obj.get("type") not in ("user", "assistant"):
            diagnostics["metadata_records"] = diagnostics.get("metadata_records", 0) + 1
        elif obj.get("type") not in ("progress", "file-history-snapshot", "queue-operation", "last-prompt"):
            diagnostics["unsupported_rows"] = diagnostics.get("unsupported_rows", 0) + 1
    return ExtractedSession(metadata=metadata, messages=messages, **diagnostics)
