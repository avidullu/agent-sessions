"""Archive status and multi-machine origin reporting."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .archive import (
    index_identity_key,
    index_record_key,
    iter_source_files,
    merge_index_records,
    read_existing_index_records,
    read_router_index_records,
    sha256_file,
    tail_sha256_file,
)
from .config import ArchiveConfig
from .portable_paths import portable_path
from .sources.registry import get_extractor


@dataclass(frozen=True)
class SourceOrigin:
    kind: str
    label: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.label}"


@dataclass(frozen=True)
class StatusSummary:
    indexed_records: int
    visible_files: int
    new_files: int
    changed_files: int
    not_visible_records: int
    skipped_sources: tuple[str, ...]
    source_counts: Counter[str]
    agent_counts: Counter[str]
    origin_counts: Counter[str]


def classify_source_origin(path: str) -> SourceOrigin:
    normalized = path.replace("/", "\\")
    windows_match = re.match(r"^([A-Za-z]):\\Users\\([^\\]+)\\", normalized, flags=re.IGNORECASE)
    if windows_match:
        drive = windows_match.group(1).upper()
        user = windows_match.group(2)
        return SourceOrigin("windows-user", f"{drive}:/Users/{user}")

    wsl_match = re.match(r"^\\\\wsl(?:\.localhost)?\\([^\\]+)\\home\\([^\\]+)\\", normalized)
    if wsl_match:
        distro = wsl_match.group(1)
        user = wsl_match.group(2)
        return SourceOrigin("wsl-user", f"{distro}:/home/{user}")

    posix_home = re.match(r"^/home/([^/]+)/", path)
    if posix_home:
        return SourceOrigin("posix-home", f"/home/{posix_home.group(1)}")

    wsl_mnt_windows = re.match(r"^/mnt/([A-Za-z])/Users/([^/]+)/", path)
    if wsl_mnt_windows:
        drive = wsl_mnt_windows.group(1).upper()
        user = wsl_mnt_windows.group(2)
        return SourceOrigin("wsl-mounted-windows-user", f"{drive}:/Users/{user}")

    return SourceOrigin("unknown", path[:80] or "<empty>")


def status_summary(config: ArchiveConfig, selected: list[str] | None = None) -> StatusSummary:
    indexed = read_existing_index_records(config)
    router_records = read_router_index_records(config)
    if router_records:
        # Merge router-produced records into the indexed view so status reflects
        # sessions routed by the VS Code extension with the same identity rules
        # used by export/index writes.
        indexed = merge_index_records(indexed, router_records)

    indexed_by_key = {index_record_key(record): record for record in indexed}
    indexed_identity_keys = {index_identity_key(record) for record in indexed}
    indexed_by_size: dict[int, list[dict[str, Any]]] = {}
    for record in indexed:
        size = record.get("size")
        if isinstance(size, int):
            indexed_by_size.setdefault(size, []).append(record)
    visible_by_key: dict[tuple[str, str], tuple[int, float, Path]] = {}
    skipped_sources: list[str] = []

    selected_names = set(selected or [])
    sources = [
        source
        for source in config.sources
        if not selected_names or source.name in selected_names or source.kind in selected_names
    ]
    source_by_name = {source.name: source for source in sources}
    for source in sources:
        if get_extractor(source.kind) is None:
            skipped_sources.append(f"{source.name} ({source.kind})")
            continue
        for path in iter_source_files(source):
            stat_result = path.stat()
            # Keyed on the portable form so stored records (normalized on load
            # and at write time) match freshly scanned live paths.
            visible_by_key[(source.name, portable_path(str(path)))] = (stat_result.st_size, stat_result.st_mtime, path)

    new_files = 0
    changed_files = 0
    for key, (size, mtime, path) in visible_by_key.items():
        idx_record: dict[str, Any] | None = indexed_by_key.get(key)
        if idx_record is None:
            # The catalog intentionally collapses byte-identical copies of the
            # same logical session even when both local paths remain visible.
            # Avoid reporting those secondary paths as perpetually new. The
            # size and tail checks keep the ordinary all-new status path cheap;
            # full hashing and extraction happen only for plausible aliases.
            same_size = indexed_by_size.get(size, [])
            if same_size:
                tail_digest = tail_sha256_file(path)
                tail_candidates = [
                    record
                    for record in same_size
                    if not record.get("tail_sha256") or record.get("tail_sha256") == tail_digest
                ]
                if tail_candidates:
                    digest = sha256_file(path)
                    digest_candidates = [
                        record for record in tail_candidates if record.get("sha256") == digest
                    ]
                    if digest_candidates:
                        source = source_by_name[key[0]]
                        extractor = get_extractor(source.kind)
                        if extractor is None:
                            new_files += 1
                            continue
                        try:
                            session = extractor(path)
                        except (OSError, TypeError, ValueError):
                            session = None
                        if session is not None:
                            candidate = {
                                "source": source.name,
                                "source_file": str(path),
                                "sha256": digest,
                                "metadata": session.metadata,
                            }
                            if index_identity_key(candidate) in indexed_identity_keys:
                                continue
            new_files += 1
            continue
        if idx_record.get("size") == size and idx_record.get("mtime") == mtime:
            prior_tail = idx_record.get("tail_sha256")
            if not prior_tail or prior_tail == tail_sha256_file(path):
                continue
        if str(idx_record.get("sha256", "")) != sha256_file(path):
            changed_files += 1

    not_visible_records = sum(1 for key in indexed_by_key if key not in visible_by_key)
    source_counts = Counter(str(record.get("source", "")) for record in indexed)
    from .utils import canonical_agent_counts

    agent_counts = canonical_agent_counts(indexed)
    # Records written (or normalized) under the portable-path convention carry
    # a username-free source_origin computed from the original absolute path;
    # classification of the stored path remains as a legacy fallback.
    origin_counts = Counter(
        str(record.get("source_origin") or classify_source_origin(str(record.get("source_file", ""))).key)
        for record in indexed
    )

    return StatusSummary(
        indexed_records=len(indexed),
        visible_files=len(visible_by_key),
        new_files=new_files,
        changed_files=changed_files,
        not_visible_records=not_visible_records,
        skipped_sources=tuple(skipped_sources),
        source_counts=source_counts,
        agent_counts=agent_counts,
        origin_counts=origin_counts,
    )


def status_to_dict(summary: StatusSummary) -> dict[str, Any]:
    return {
        "indexed_records": summary.indexed_records,
        "visible_files": summary.visible_files,
        "new_files": summary.new_files,
        "changed_files": summary.changed_files,
        "not_visible_records": summary.not_visible_records,
        "skipped_sources": list(summary.skipped_sources),
        "source_counts": dict(summary.source_counts),
        "agent_counts": dict(summary.agent_counts),
        "origin_counts": dict(summary.origin_counts),
    }


def render_status(summary: StatusSummary) -> str:
    lines = [
        "# Archive Status",
        "",
        f"- Indexed records: `{summary.indexed_records}`",
        f"- Visible configured files: `{summary.visible_files}`",
        f"- New visible files: `{summary.new_files}`",
        f"- Changed visible files: `{summary.changed_files}`",
        f"- Indexed records not visible from this machine: `{summary.not_visible_records}`",
        "",
        "## Origin Environments",
        "",
        "| Origin | Records |",
        "| --- | ---: |",
    ]
    if summary.origin_counts:
        for origin, count in summary.origin_counts.most_common():
            lines.append(f"| `{origin}` | {count} |")
    else:
        lines.append("| _none_ | 0 |")

    lines.extend(["", "## Agents (canonical)", "", "| Agent | Records |", "| --- | ---: |"])
    if summary.agent_counts:
        for agent, count in summary.agent_counts.most_common():
            lines.append(f"| `{agent}` | {count} |")
    else:
        lines.append("| _none_ | 0 |")

    lines.extend(["", "## Sources (per-machine)", "", "| Source | Records |", "| --- | ---: |"])
    if summary.source_counts:
        for source, count in summary.source_counts.most_common():
            lines.append(f"| `{source}` | {count} |")
    else:
        lines.append("| _none_ | 0 |")

    if summary.skipped_sources:
        lines.extend(["", "## Skipped Sources", ""])
        for source in summary.skipped_sources:
            lines.append(f"- `{source}`")

    lines.append("")
    return "\n".join(lines)


def archive_status(config: ArchiveConfig, selected: list[str] | None = None, as_json: bool = False) -> int:
    summary = status_summary(config, selected=selected)
    if as_json:
        print(json.dumps(status_to_dict(summary), indent=2, sort_keys=True))
    else:
        print(render_status(summary))
    return 0
