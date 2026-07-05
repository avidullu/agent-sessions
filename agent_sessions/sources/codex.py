"""Codex JSONL session extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ExtractedSession, SessionMessage
from ..utils import jsonl_objects, session_id_from_name, text_from_content
from .registry import register


@register("codex")
def extract(path: Path) -> ExtractedSession:
    metadata: dict[str, Any] = {"session_id": session_id_from_name(path)}
    messages: list[SessionMessage] = []
    for obj in jsonl_objects(path):
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        if obj.get("type") == "session_meta":
            metadata.update(
                {
                    "session_id": payload.get("session_id") or payload.get("id") or metadata["session_id"],
                    "cwd": payload.get("cwd"),
                    "model_provider": payload.get("model_provider"),
                    "cli_version": payload.get("cli_version"),
                    "source": payload.get("source"),
                }
            )
            continue
        role = payload.get("role")
        content = text_from_content(payload.get("content"))
        if role and content:
            messages.append(SessionMessage(role=role, text=content, timestamp=obj.get("timestamp", "")))
    return ExtractedSession(metadata=metadata, messages=messages)
