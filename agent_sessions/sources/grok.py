"""Grok local session extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ExtractedSession, SessionMessage
from ..utils import jsonl_objects, text_from_content
from .registry import register

_TOOL_CALL_KEYS = ("tool_calls", "toolCalls", "tool_call", "function_call", "functionCall")
_TOOL_PART_TYPES = frozenset({"tool_use", "tool_call", "function_call"})


def _note(diagnostics: dict[str, int], key: str) -> None:
    diagnostics[key] = diagnostics.get(key, 0) + 1


def _role_name(obj: dict[str, Any]) -> str:
    for key in ("role", "type"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip() and value.strip().lower() != "message":
            return value.strip().lower()
    return ""


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return value is not None and not isinstance(value, bool)


def _has_encrypted_content(obj: dict[str, Any]) -> bool:
    if _nonempty(obj.get("encrypted_content")):
        return True
    message = obj.get("message")
    return isinstance(message, dict) and _nonempty(message.get("encrypted_content"))


def _is_assistant_or_tool(obj: dict[str, Any]) -> bool:
    roles = [_role_name(obj)]
    message = obj.get("message")
    if isinstance(message, dict):
        roles.append(_role_name(message))
    return any(role == "assistant" or role == "tool" or role.startswith("tool_") for role in roles)


def _has_tool_calls(obj: dict[str, Any]) -> bool:
    if any(_nonempty(obj.get(key)) for key in _TOOL_CALL_KEYS):
        return True
    content = obj.get("content")
    if isinstance(content, list) and any(
        isinstance(part, dict) and part.get("type") in _TOOL_PART_TYPES for part in content
    ):
        return True
    message = obj.get("message")
    return isinstance(message, dict) and message is not obj and _has_tool_calls(message)


def _dropped_without_text(obj: dict[str, Any]) -> bool:
    # Ciphertext and tool-only rows are not transcripts. Counting them makes export partial.
    return _has_encrypted_content(obj) or (_is_assistant_or_tool(obj) and _has_tool_calls(obj))


@register("grok")
def extract(path: Path, *, source_path: Path | None = None) -> ExtractedSession:
    identity = source_path if source_path is not None else path
    metadata: dict[str, Any] = {"session_id": identity.parent.name, "project": identity.parent.parent.name}
    messages: list[SessionMessage] = []
    diagnostics: dict[str, int] = {}
    for obj in jsonl_objects(path, diagnostics=diagnostics):
        content = text_from_content(obj.get("content"))
        if not content:
            if _dropped_without_text(obj):
                _note(diagnostics, "unsupported_rows")
            elif obj.get("type") in ("metadata", "session_meta"):
                _note(diagnostics, "metadata_records")
            elif not any(key in obj for key in ("content", "type", "source", "role")):
                _note(diagnostics, "unsupported_rows")
            continue
        role = obj.get("type") or "message"
        messages.append(SessionMessage(role=role, text=content, timestamp=obj.get("timestamp", "")))
    return ExtractedSession(metadata=metadata, messages=messages, **diagnostics)
