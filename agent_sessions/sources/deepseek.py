"""DeepSeek VS Code request dump extraction."""

from __future__ import annotations

from pathlib import Path

from ..models import ExtractedSession, SessionMessage
from .registry import register


@register("deepseek_request_dump")
def extract(path: Path) -> ExtractedSession:
    metadata = {"session_id": path.parent.name, "request_file": path.name}
    text = path.read_text(encoding="utf-8", errors="replace")
    messages = [SessionMessage(role="request-prompt", text=text)] if text.strip() else []
    return ExtractedSession(metadata=metadata, messages=messages)
