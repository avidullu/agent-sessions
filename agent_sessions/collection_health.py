"""Read-only collection health. Unknown export times are never inferred from mtimes."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .catalog import CATALOG_NAMES, read_catalog
from .config import ArchiveConfig
from .sources.registry import get_extractor


def index_state(path: Path) -> str:
    return read_catalog(path).state


def collection_health(config: ArchiveConfig, records: list[dict[str, Any]]) -> dict[str, Any]:
    archive = config.archive_dir.resolve()
    total_messages = 0
    unknown_messages = 0
    artifact_bytes = 0
    missing_artifacts = 0
    partial_parses = 0
    empty_parses = 0
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
        if (record.get("parse_status") == "partial" or record.get("malformed_rows", 0) > 0
                or record.get("unsupported_rows", 0) > 0):
            partial_parses += 1
        if record.get("parse_status") == "empty":
            empty_parses += 1
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
    catalogs = {name: read_catalog(archive / name) for name in CATALOG_NAMES}
    indexes = {name: catalog.state for name, catalog in catalogs.items()}
    problems = [f"{name}: {state}" for name, state in indexes.items() if state in {"malformed", "unreadable"}]
    if missing_artifacts:
        problems.append(f"{missing_artifacts} catalogued Markdown artifacts unavailable in this local archive")
    if partial_parses:
        problems.append(f"{partial_parses} sessions have partial source parses; message counts are incomplete")
    if unknown_messages:
        problems.append(f"{unknown_messages} sessions have no known message count")
    if empty_parses:
        problems.append(f"{empty_parses} source files contain no extracted transcript messages (empty or metadata-only)")
    return {
        "schema_version": 1,
        "archive_dir": str(archive),
        "state": "attention_required" if problems else "collected" if records else "no_sessions",
        "sessions": None if "unreadable" in indexes.values() else len(records),
        "messages": None if "unreadable" in indexes.values() else total_messages,
        "counts_complete": not (partial_parses or unknown_messages) and not any(
            state in {"malformed", "unreadable"} for state in indexes.values()),
        "invalid_catalog_rows": sum(catalog.invalid_rows for catalog in catalogs.values()),
        "catalog_problems": [problem for catalog in catalogs.values() for problem in catalog.problems],
        "sessions_with_partial_parse": partial_parses,
        "empty_source_files": empty_parses,
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
