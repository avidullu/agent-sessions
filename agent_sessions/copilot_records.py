"""Read-only log normalization. Stdlib-only so the same reader can run over SSH.

No reasoning blocks or internal instructions are emitted. Source logs are data,
never executable instructions. This module deliberately does not use the lossy
Markdown exporters or change their public model.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def timestamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return ""
        return parsed.astimezone(UTC).isoformat()
    except ValueError:
        return ""


def text_parts(content: Any) -> str:
    if isinstance(content, str):
        # Inline reasoning blocks must not survive older text-only exporters.
        return re.sub(r"<think>.*?(?:</think>|$)", "", content, flags=re.S).strip()
    if isinstance(content, list):
        return "\n".join(
            text_parts(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text")
        ).strip()
    return ""


def events(obj: dict[str, Any], kind: str) -> Iterator[dict[str, str]]:
    """Preserve tool linkage while ignoring parallel summaries/transport events."""
    at = timestamp(obj.get("timestamp"))
    if kind == "codex":
        if obj.get("type") != "response_item":
            return
        item = obj.get("payload", {})
        if not isinstance(item, dict) or item.get("channel") == "analysis":
            return
        category = item.get("type")
        role = item.get("role")
        if category == "message" and role in ("user", "assistant"):
            yield {"role": role, "text": text_parts(item.get("content")), "timestamp": at, "call_id": ""}
        elif category in ("function_call", "custom_tool_call"):
            yield {
                "role": "tool_call",
                "text": str(item.get("name", "")) + " " + str(item.get("arguments", item.get("input", ""))),
                "timestamp": at,
                "call_id": str(item.get("call_id", "")),
            }
        elif category in ("function_call_output", "custom_tool_call_output"):
            output = item.get("output", "")
            yield {
                "role": "tool_result",
                "text": output if isinstance(output, str) else json.dumps(output),
                "timestamp": at,
                "call_id": str(item.get("call_id", "")),
            }
    elif kind == "claude":
        item = obj.get("message", {})
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            return
        role = item["role"]
        content = item.get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if not isinstance(content, list):
            return
        for part in content:
            if not isinstance(part, dict):
                continue
            category = part.get("type")
            if category == "text":
                yield {"role": role, "text": text_parts(part.get("text")), "timestamp": at, "call_id": ""}
            elif category == "tool_use":
                yield {
                    "role": "tool_call",
                    "text": str(part.get("name", "")) + " " + json.dumps(part.get("input", {})),
                    "timestamp": at,
                    "call_id": str(part.get("id", "")),
                }
            elif category == "tool_result":
                yield {
                    "role": "tool_result",
                    "text": text_parts(part.get("content")),
                    "timestamp": at,
                    "call_id": str(part.get("tool_use_id", "")),
                }
    elif kind == "grok":
        role = obj.get("type") or obj.get("role")
        if role in ("user", "assistant", "tool_result"):
            yield {
                "role": role,
                "text": text_parts(obj.get("content")),
                "timestamp": at,
                "call_id": str(obj.get("tool_call_id", "")),
            }


def read_session(path: Path, kind: str) -> dict[str, Any]:
    before = path.stat()
    session_id = path.stem if kind != "grok" else path.parent.name
    parent = ""
    project = "unknown"
    messages: list[dict[str, str]] = []
    malformed = 0
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for number, line in enumerate(stream, 1):
            sha.update(line)
            try:
                obj = json.loads(line)
            except (ValueError, UnicodeError):
                malformed += 1
                continue
            if not isinstance(obj, dict):
                malformed += 1
                continue
            metadata = obj.get("payload", {}) if obj.get("type") == "session_meta" else obj
            if not isinstance(metadata, dict):
                metadata = {}
            session_id = str(
                metadata.get("sessionId")
                or metadata.get("session_id")
                or (metadata.get("id") if obj.get("type") == "session_meta" else None)
                or session_id
            )
            parent = str(
                metadata.get("forked_from_id")
                or metadata.get("parent_session_id")
                or metadata.get("parentSessionId")
                or parent
            )
            cwd = metadata.get("cwd")
            if isinstance(cwd, str) and cwd:
                project = cwd.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            for event in events(obj, kind):
                if event["text"]:
                    event["event_id"] = f"{kind}:{session_id}:{number}:{len(messages)}"
                    messages.append(event)
    if kind == "claude" and path.parent.name == "subagents":
        parent = path.parent.parent.name
    after = path.stat()
    stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return {
        "schema": "agent-session-record.v1",
        "session_id": f"{kind}:{session_id}",
        "parent_id": f"{kind}:{parent}" if parent else "",
        "project": project,
        "source_sha256": sha.hexdigest(),
        "source_file": str(path),
        "kind": kind,
        "stable": stable,
        "malformed_rows": malformed,
        "messages": messages,
    }


def scan(
    root: Path, kind: str, *, settled_seconds: int = 3600, max_file_bytes: int = 64 * 1024 * 1024
) -> Iterator[dict[str, Any]]:
    if kind not in ("codex", "claude", "grok"):
        raise ValueError("supported raw sources: codex, claude, grok")
    if not root.is_dir():
        raise ValueError("source root does not exist")
    pattern = "chat_history.jsonl" if kind == "grok" else "*.jsonl"
    for path in sorted(root.rglob(pattern)):
        if path.is_symlink() or time.time() - path.stat().st_mtime < settled_seconds:
            continue
        if path.stat().st_size > max_file_bytes:
            yield {"stable": False, "skip_reason": "oversized_source", "source_file": str(path)}
            continue
        yield read_session(path, kind)
