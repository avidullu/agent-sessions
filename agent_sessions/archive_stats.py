"""Explicit catalog and independent-backup metrics, without transcript excerpts."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import zlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .archive import read_existing_index_records
from .backup import compression_mode, object_path, open_object, snapshots
from .config import ArchiveConfig
from .utils import canonical_agent


def catalog_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    sessions: set[tuple[str, str]] = set()
    sizes: list[int] = []
    missing_ids = 0
    months: Counter[str] = Counter()
    for row in records:
        metadata = row.get("metadata") or {}
        session_id = metadata.get("session_id") if isinstance(metadata, dict) else None
        if session_id:
            sessions.add((canonical_agent(row), str(session_id)))
        else:
            missing_ids += 1
        size = row.get("size")
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
            sizes.append(size)
        try:
            month = datetime.fromtimestamp(float(row["mtime"]), UTC).strftime("%Y-%m")
        except (KeyError, ValueError, TypeError, OverflowError, OSError):
            month = "unknown"
        months[month] += 1
    sizes.sort()
    percentiles = {f"p{p}": sizes[max(0, math.ceil(len(sizes) * p / 100) - 1)] if sizes else None
                   for p in (50, 90, 99, 100)}
    return {
        "catalog_records": len(records), "distinct_identified_sessions": len(sessions),
        "records_without_session_id": missing_ids,
        "messages": sum(row.get("messages", 0) for row in records if isinstance(row.get("messages", 0), int)),
        "record_source_bytes": sum(sizes), "records_without_size": len(records) - len(sizes),
        "source_size_percentiles_bytes": percentiles,
        "agents": dict(Counter(canonical_agent(row) for row in records).most_common()),
        "sources": dict(Counter(str(row.get("source", "unknown")) for row in records).most_common()),
        "source_modified_months_utc": dict(sorted(months.items())),
    }


def backup_metrics(root: Path) -> dict[str, Any]:
    objects: dict[str, int] = {}
    versions: dict[tuple[str, str, str], int] = {}
    catalogs: dict[tuple[str, ...], dict[str, Any]] = {}
    paths: set[str] = set()
    missing: set[str] = set()
    content_sizes: dict[str, int] = {}
    count = 0
    parsed_catalogs: set[str] = set()
    parsed_raw: set[str] = set()
    decoded_originals: set[str] = set()
    unreadable_raw_gzip: set[str] = set()
    for _, snapshot in snapshots(root):
        count += 1
        for entry in snapshot["files"]:
            key = entry["sha256"]
            obj = object_path(root, key)
            versions[(snapshot["machine"], entry["path"], key)] = entry["bytes"]
            content_sizes[key] = entry["bytes"]
            if obj.is_file():
                paths.add(entry["path"].replace("\\", "/"))
            if not obj.is_file():
                missing.add(key)
                continue
            objects[key] = obj.stat().st_size
            if entry["category"] == "raw" and entry["path"].endswith(".gz") and key not in parsed_raw:
                parsed_raw.add(key)
                try:
                    with open_object(obj) as stored, gzip.GzipFile(fileobj=stored, mode="rb") as original:
                        decoded_originals.add(hashlib.file_digest(original, "sha256").hexdigest())
                except (OSError, EOFError, zlib.error):
                    unreadable_raw_gzip.add(key)
            if (entry["category"] == "archive" and Path(entry["path"].replace("\\", "/")).name == "index.jsonl"
                    and key not in parsed_catalogs):
                parsed_catalogs.add(key)
                with open_object(obj) as stream:
                    lines = stream.read().decode("utf-8").splitlines()
                for line in lines:
                    row = json.loads(line)
                    metadata = row.get("metadata") or {}
                    sid = metadata.get("session_id") if isinstance(metadata, dict) else None
                    identity = (canonical_agent(row), str(sid), str(row.get("sha256"))) if sid else (
                        str(row.get("source")), str(row.get("source_file")), str(row.get("sha256")))
                    catalogs[identity] = row
    rows = list(catalogs.values())
    raw_covered = 0
    transcript_covered = 0
    for row in rows:
        raw = str(row.get("raw") or "").replace("\\", "/").lstrip("/")
        markdown = str(row.get("markdown") or "").replace("\\", "/").lstrip("/")
        has_raw = (row.get("sha256") in objects or row.get("sha256") in decoded_originals
                   or bool(raw and any(p.endswith("/" + raw) for p in paths)))
        raw_covered += has_raw
        transcript_covered += has_raw or bool(markdown and any(p.endswith("/" + markdown) for p in paths))
    logical = sum(versions.values())
    physical = sum(objects.values())
    content = sum(content_sizes.values())
    available_content = sum(content_sizes[key] for key in objects)
    all_objects = [p for p in (root / "objects").rglob("*") if p.is_file() and not p.is_symlink()]
    return {
        "snapshots": count, "distinct_file_paths": len({k[:2] for k in versions}),
        "file_versions": len(versions), "unique_objects": len(objects), "missing_objects": len(missing),
        "logical_file_version_bytes": logical, "stored_object_bytes": physical,
        "object_directory_bytes": sum(p.stat().st_size for p in all_objects),
        "unreferenced_object_files": len(all_objects) - len(objects),
        "unique_content_bytes": content, "compression": compression_mode(root),
        "deduplication_saved_fraction": 1 - content / logical if logical else 0.0,
        "compression_saved_fraction": 1 - physical / available_content if available_content else 0.0,
        "catalog_history": catalog_metrics(rows),
        "catalog_records_with_raw_or_original": raw_covered,
        "catalog_records_with_raw_or_rendered_transcript": transcript_covered,
        "catalog_records_without_preserved_transcript": len(rows) - transcript_covered,
        "decoded_raw_gzip_originals": len(decoded_originals),
        "unreadable_raw_gzip_objects": len(unreadable_raw_gzip),
        "integrity": "Inventory plus decoded raw-gzip hashes for coverage; run backup verify for full integrity.",
    }


def archive_statistics(config: ArchiveConfig, root: Path | None = None) -> dict[str, Any]:
    rows = read_existing_index_records(config)
    report: dict[str, Any] = {"schema_version": 1, "catalog": catalog_metrics(rows),
                              "catalog_scope": "current local catalog"}
    available: dict[str, int] = {}
    missing = 0
    for row in rows:
        name = row.get("markdown")
        if not name or not (config.repo_root / name).is_file():
            missing += 1
        else:
            available[name] = (config.repo_root / name).stat().st_size
    report["local_artifacts"] = {"unique_markdown_files": len(available), "markdown_bytes": sum(available.values()),
                                 "records_missing_markdown": missing}
    if root is not None:
        report["backup"] = backup_metrics(root)
        if not rows:
            report["catalog"] = report["backup"]["catalog_history"]
            report["catalog_scope"] = "all retained backup catalogs (no local catalog available)"
    return report


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:,.2f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")


def render_statistics(report: dict[str, Any]) -> str:
    catalog = report["catalog"]
    lines = ["# Agent session archive statistics", "", f"Catalog scope: {report['catalog_scope']}.", "",
             f"- Catalog records: **{catalog['catalog_records']:,}**",
             f"- Distinct identified sessions (agent + session ID): **{catalog['distinct_identified_sessions']:,}**",
             f"- Records without session ID: {catalog['records_without_session_id']:,}",
             f"- Messages across catalog records: {catalog['messages']:,}",
             f"- Source bytes summed across records: {human_bytes(catalog['record_source_bytes'])}",
             f"- Records without size metadata: {catalog['records_without_size']:,}",
             f"- Local records missing Markdown: {report['local_artifacts']['records_missing_markdown']:,}",
             "", "Session IDs can span subagent files and versions; records and messages are not deduplicated sessions.",
             "", "## Source file size percentiles (known sizes, nearest rank)", ""]
    for key, value in catalog["source_size_percentiles_bytes"].items():
        lines.append(f"- {key}: {human_bytes(value) if value is not None else 'unknown'}")
    for key, label in (("agents", "Agents"), ("sources", "Sources"),
                       ("source_modified_months_utc", "Source modification month (UTC)")):
        lines.extend(["", f"## {label}", "", "| Group | Records | Share |", "| --- | ---: | ---: |"])
        for name, count in catalog[key].items():
            safe = str(name).replace("|", "\\|").replace("\n", " ").replace("<", "&lt;")
            share = count / catalog["catalog_records"] if catalog["catalog_records"] else 0
            lines.append(f"| {safe} | {count:,} | {share:.1%} |")
    if "backup" in report:
        b = report["backup"]
        lines.extend(["", "## Independent backup", "",
                      f"- Snapshots: {b['snapshots']:,}; file versions: {b['file_versions']:,}",
                      f"- Unique objects: {b['unique_objects']:,}; missing objects: {b['missing_objects']:,}",
                      f"- Referenced stored object bytes: {human_bytes(b['stored_object_bytes'])}",
                      f"- Object-directory bytes: {human_bytes(b['object_directory_bytes'])}",
                      f"- Unreferenced object files (e.g. interrupted runs): {b['unreferenced_object_files']:,}",
                      f"- Logical file-version bytes: {human_bytes(b['logical_file_version_bytes'])}",
                      f"- Deduplication saving: {b['deduplication_saved_fraction']:.1%}",
                      f"- Compression ({b['compression']}) saving on unique content: {b['compression_saved_fraction']:.1%}",
                      f"- Historical catalog records: {b['catalog_history']['catalog_records']:,}",
                      f"- Historical identified sessions: {b['catalog_history']['distinct_identified_sessions']:,}",
                      f"- Records with raw/original: {b['catalog_records_with_raw_or_original']:,}",
                      f"- Records with raw or rendered transcript: {b['catalog_records_with_raw_or_rendered_transcript']:,}",
                      f"- Records without preserved transcript: {b['catalog_records_without_preserved_transcript']:,}",
                      f"- Raw gzip objects that could not be decoded: {b['unreadable_raw_gzip_objects']:,}",
                      "", b["integrity"]])
    return "\n".join(lines) + "\n"
