"""Read-only collection health. Unknown export times are never inferred from mtimes."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .config import ArchiveConfig
from .sources.registry import get_extractor


def index_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict) or not all(key in record for key in ("source", "source_file")):
                    return "malformed"
    except (ValueError, UnicodeError):
        return "malformed"
    except OSError:
        return "unreadable"
    return "readable"


def collection_health(config: ArchiveConfig, records: list[dict[str, Any]]) -> dict[str, Any]:
    archive = config.archive_dir.resolve()
    total_messages = 0
    unknown_messages = 0
    artifact_bytes = 0
    missing_artifacts = 0
    export_times: list[dt.datetime] = []
    sources: dict[str, str] = {}
    for source in config.sources:
        if get_extractor(source.kind) is None:
            sources[source.name] = "inventory_only"
        elif not any(root.exists() for root in source.roots):
            sources[source.name] = "roots_missing"
        else:
            sources[source.name] = "available"
    for source in config.disabled_sources:
        sources[source.name] = "router_managed" if source.kind == "router_index" else "disabled"
    for record in records:
        count = record.get("messages")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            total_messages += count
        else:
            unknown_messages += 1
        raw = record.get("markdown")
        if isinstance(raw, str) and raw:
            # Catalogs can come from other machines. Never follow a catalog path
            # (including a symlink) outside this configured local archive.
            try:
                artifact = (config.repo_root / raw.replace("\\", "/")).resolve()
                if not artifact.is_relative_to(archive) or not artifact.is_file():
                    missing_artifacts += 1
                else:
                    artifact_bytes += artifact.stat().st_size
            except (OSError, ValueError, RuntimeError):
                missing_artifacts += 1
        else:
            missing_artifacts += 1
        exported_at = record.get("exported_at")
        if isinstance(exported_at, str):
            try:
                timestamp = dt.datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
                if timestamp.tzinfo is not None:
                    export_times.append(timestamp.astimezone(dt.UTC))
            except ValueError:
                pass
    indexes = {name: index_state(archive / name) for name in ("index.jsonl", ".router-index.jsonl")}
    problems = [f"{name}: {state}" for name, state in indexes.items() if state in {"malformed", "unreadable"}]
    if missing_artifacts:
        problems.append(f"{missing_artifacts} catalogued Markdown artifacts unavailable in this local archive")
    return {
        "schema_version": 1,
        "archive_dir": str(archive),
        "state": "attention_required" if problems else "collected" if records else "no_sessions",
        "sessions": None if "unreadable" in indexes.values() else len(records),
        "messages": None if "unreadable" in indexes.values() else total_messages,
        "counts_complete": not any(state in {"malformed", "unreadable"} for state in indexes.values()),
        "sessions_with_unknown_message_count": unknown_messages,
        "local_markdown_bytes": artifact_bytes,
        "missing_local_artifacts": missing_artifacts,
        "last_successful_export": max(export_times).isoformat() if export_times else None,
        "indexes": indexes,
        "sources": sources,
        "problems": problems,
        "router_watcher": "unknown_use_router_collection_status",
        "hint": "Match agentSessionRouter.outputDir to archive_dir. Router auto-export is opt-in.",
    }
