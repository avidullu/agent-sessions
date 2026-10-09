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
    diagnostics: dict[str, int] = {}
    for obj in jsonl_objects(path, diagnostics=diagnostics):
        content = text_from_content(obj.get("content"))
        if not content:
            if obj.get("type") in ("metadata", "session_meta"):
                diagnostics["metadata_records"] = diagnostics.get("metadata_records", 0) + 1
            elif not any(key in obj for key in ("content", "type", "source", "role")):
                diagnostics["unsupported_rows"] = diagnostics.get("unsupported_rows", 0) + 1
            continue
        role = obj.get("type") or "message"
        messages.append(SessionMessage(role=role, text=content, timestamp=obj.get("timestamp", "")))
    return ExtractedSession(metadata=metadata, messages=messages, **diagnostics)
