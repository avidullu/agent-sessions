"""Small utility functions shared across archive modules."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Iterable


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def jsonl_objects(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def text_from_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(text_from_content(item.get("text")))
                elif "content" in item:
                    parts.append(text_from_content(item.get("content")))
                elif "input" in item:
                    parts.append(text_from_content(item.get("input")))
        return "\n".join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ("text", "content", "message", "input", "output"):
            if key in value:
                return text_from_content(value[key])
    return ""


def session_id_from_name(path: Path) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path.name, re.I)
    return match.group(1) if match else path.stem


def archive_markdown_path(repo_root: Path, markdown: str) -> Path:
    """Resolve an archive markdown path from index.jsonl (may use Windows separators)."""
    normalized = markdown.replace("\\", "/")
    return repo_root / normalized


def slugify(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^\w.\- ]+", "-", value, flags=re.ASCII)
    value = re.sub(r"\s+", "-", value.strip())
    value = value.strip(".-_")
    return (value[:max_len].strip(".-_") or "session").lower()
