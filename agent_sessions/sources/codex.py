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
    diagnostics: dict[str, int] = {}
    for obj in jsonl_objects(path, diagnostics=diagnostics):
        payload_raw = obj.get("payload")
        payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}
        if obj.get("type") == "session_meta":
            diagnostics["metadata_records"] = diagnostics.get("metadata_records", 0) + 1
            if not isinstance(payload_raw, dict):
                diagnostics["unsupported_rows"] = diagnostics.get("unsupported_rows", 0) + 1
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
        if isinstance(role, str) and role and content:
            messages.append(SessionMessage(role=role, text=content, timestamp=obj.get("timestamp", "")))
        elif not (isinstance(role, str) and role) and obj.get("type") not in ("event_msg", "turn_context") and payload.get("type") not in (
            "function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output", "reasoning"
        ):
            diagnostics["unsupported_rows"] = diagnostics.get("unsupported_rows", 0) + 1
    return ExtractedSession(metadata=metadata, messages=messages, **diagnostics)
