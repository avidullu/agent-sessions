"""Report-only handoff coverage audit for baseline knowledge work."""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .baseline_settings import load_baseline_settings
from .config import ArchiveConfig
from .utils import archive_markdown_path, read_jsonl_dicts


DEFAULT_AUDIT_PATH = Path("baseline/handoffs/audit.md")
HANDOFF_FILENAMES = ("SESSION_HANDOFF.md", "session-handoff.md")
MEMORY_FILENAMES = ("MEMORY.md", "memory/MEMORY.md")
MEMORY_HANDOFF_PATHS = ("memory/session-handoff.md", "memory/SESSION_HANDOFF.md")
EXPECTED_HEADINGS = (
    "You Are Here",
    "Next Steps / Open Threads",
    "Ramp-Up Kit",
    "Key Decisions",
)
HANDOFF_TERMS = (
    "session handoff",
    "session-handoff",
    "start here",
    "ramp-up kit",
    "next steps / open threads",
)


@dataclass(frozen=True)
class RepoHandoffAudit:
    path: str
    kind: str
    modified_at: str | None
    freshness: str
    sections: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ArchiveHandoffHit:
    source: str
    markdown_path: str
    session_id: str | None
    project_raw: str | None
    sections: tuple[str, ...]
    signals: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class HandoffAudit:
    generated_at: str
    stale_days: int
    archive_index_present: bool
    archive_records_available: int
    archive_records_scanned: int
    repo_files: tuple[RepoHandoffAudit, ...]
    archive_hits: tuple[ArchiveHandoffHit, ...]
    missing_expected_paths: tuple[str, ...]


def baseline_handoffs_audit(
    config: ArchiveConfig,
    output: Path | None = None,
    stale_days: int = 90,
    max_archive_records: int = 0,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    target = output or settings.root / "handoffs" / "audit.md"
    if not target.is_absolute():
        target = config.repo_root / target
    audit = build_handoff_audit(
        config,
        stale_days=stale_days,
        max_archive_records=max_archive_records,
    )
    report = render_handoff_audit(audit)
    if dry_run:
        print(report)
        print(f"Would write {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote {target}")
    return 0


def build_handoff_audit(
    config: ArchiveConfig,
    stale_days: int = 90,
    max_archive_records: int = 0,
    now: dt.datetime | None = None,
) -> HandoffAudit:
    now = now or dt.datetime.now(dt.timezone.utc)
    archive_index = config.archive_dir / "index.jsonl"
    archive_index_present = archive_index.exists()
    records = read_jsonl_dicts(archive_index, label="archive/index.jsonl") if archive_index_present else []
    records_to_scan = records if max_archive_records <= 0 else records[:max_archive_records]
    return HandoffAudit(
        generated_at=now.isoformat(timespec="seconds"),
        stale_days=stale_days,
        archive_index_present=archive_index_present,
        archive_records_available=len(records),
        archive_records_scanned=len(records_to_scan),
        repo_files=tuple(analyze_repo_handoff(path, config.repo_root, stale_days, now) for path in repo_handoff_paths(config.repo_root)),
        archive_hits=tuple(scan_archive_handoff_hits(config, records_to_scan)),
        missing_expected_paths=missing_expected_paths(config.repo_root),
    )


def repo_handoff_paths(repo_root: Path) -> tuple[Path, ...]:
    candidates = [
        *(repo_root / name for name in HANDOFF_FILENAMES),
        *(repo_root / name for name in MEMORY_FILENAMES),
        *(repo_root / name for name in MEMORY_HANDOFF_PATHS),
    ]
    seen: set[Path] = set()
    existing: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.exists() or not path.is_file():
            continue
        seen.add(resolved)
        existing.append(path)
    return tuple(existing)


def missing_expected_paths(repo_root: Path) -> tuple[str, ...]:
    root_handoffs = [repo_root / name for name in HANDOFF_FILENAMES]
    missing: list[str] = []
    if not any(path.exists() for path in root_handoffs):
        missing.append("SESSION_HANDOFF.md or session-handoff.md")
    memory_files = [repo_root / name for name in MEMORY_FILENAMES]
    if any(path.exists() for path in memory_files):
        memory_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in memory_files if path.exists())
        if not has_start_here_pointer(memory_text):
            missing.append("MEMORY.md start-here pointer to session handoff")
    return tuple(missing)


def analyze_repo_handoff(path: Path, repo_root: Path, stale_days: int, now: dt.datetime) -> RepoHandoffAudit:
    text = path.read_text(encoding="utf-8", errors="replace")
    relative = path.relative_to(repo_root).as_posix()
    modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    age_days = max(0, (now - modified).days)
    warnings: list[str] = []
    sections = handoff_sections(text)
    if age_days > stale_days:
        warnings.append(f"stale: modified {age_days} days ago")
    if path.name.lower() == "memory.md":
        kind = "memory-start-here"
        if not has_start_here_pointer(text):
            warnings.append("missing start-here pointer to session handoff")
    else:
        kind = "repo-handoff"
        missing = [heading for heading in EXPECTED_HEADINGS if heading not in sections]
        warnings.extend(f"missing heading: {heading}" for heading in missing)
    freshness = "stale" if age_days > stale_days else "fresh"
    return RepoHandoffAudit(
        path=relative,
        kind=kind,
        modified_at=modified.isoformat(timespec="seconds"),
        freshness=freshness,
        sections=sections,
        warnings=tuple(warnings),
    )


def scan_archive_handoff_hits(config: ArchiveConfig, records: list[dict[str, Any]]) -> list[ArchiveHandoffHit]:
    hits: list[ArchiveHandoffHit] = []
    for record in records:
        markdown = str(record.get("markdown", ""))
        if not markdown:
            continue
        markdown_path = archive_markdown_path(config.repo_root, markdown)
        if not markdown_path.exists():
            continue
        text = markdown_path.read_text(encoding="utf-8", errors="replace")
        if not is_probable_handoff(text, markdown_path):
            continue
        hits.append(archive_handoff_hit(record, text, markdown))
    return hits


def archive_handoff_hit(record: dict[str, Any], text: str, markdown: str) -> ArchiveHandoffHit:
    metadata = record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    sections = handoff_sections(text)
    signals = handoff_signals(text)
    warnings = tuple(["no standard handoff headings"] if not sections else [])
    return ArchiveHandoffHit(
        source=str(record.get("source", "unknown")),
        markdown_path=markdown.replace("\\", "/"),
        session_id=optional_str(metadata.get("session_id") or metadata.get("id")),
        project_raw=optional_str(metadata.get("project") or metadata.get("cwd")),
        sections=sections,
        signals=signals,
        warnings=warnings,
    )


def optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def handoff_sections(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for heading in EXPECTED_HEADINGS:
        pattern = rf"^#+\s+{re.escape(heading)}\s*$"
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            found.append(heading)
    return tuple(found)


def handoff_signals(text: str) -> tuple[str, ...]:
    lower = text.lower()
    return tuple(term for term in HANDOFF_TERMS if term in lower)


def has_start_here_pointer(text: str) -> bool:
    for line in text.splitlines():
        lower = line.lower()
        if "start here" in lower and ("session-handoff" in lower or "session_handoff" in lower):
            return True
    return False


def is_probable_handoff(text: str, path: Path) -> bool:
    name = path.name.lower()
    if name in {"session_handoff.md", "session-handoff.md", "session_handoff.txt"}:
        return True
    lower = text.lower()
    if "session handoff" in lower or "session-handoff" in lower:
        return True
    return len(handoff_sections(text)) >= 2


def render_handoff_audit(audit: HandoffAudit) -> str:
    repo_warning_count = sum(1 for item in audit.repo_files if item.warnings)
    archive_warning_count = sum(1 for item in audit.archive_hits if item.warnings)
    lines = [
        f"# Baseline Handoff Audit ({audit.generated_at[:10]})",
        "",
        "> K2 report-only output. This command writes only `baseline/handoffs/audit.md` by default; "
        "K6 owns `baseline/handoffs/index.jsonl`, project-page feeds, and proposal writes.",
        "",
        "## Summary",
        "",
        f"- Repo handoff files found: `{len(audit.repo_files)}`",
        f"- Missing expected repo pointers: `{len(audit.missing_expected_paths)}`",
        f"- Repo handoffs with warnings: `{repo_warning_count}`",
        f"- Archive index present: `{yes_no(audit.archive_index_present)}`",
        f"- Archive records scanned: `{audit.archive_records_scanned}` of `{audit.archive_records_available}`",
        f"- Archive handoff candidates: `{len(audit.archive_hits)}`",
        f"- Archive handoff candidates with warnings: `{archive_warning_count}`",
        f"- Stale threshold: `{audit.stale_days}` days",
        "",
    ]
    lines.extend(render_repo_section(audit))
    lines.extend(render_archive_section(audit))
    lines.extend(render_gaps_section(audit))
    return "\n".join(lines).rstrip() + "\n"


def render_repo_section(audit: HandoffAudit) -> list[str]:
    lines = ["## Repo Handoffs", ""]
    if not audit.repo_files:
        return lines + ["- No repo handoff files found.", ""]
    lines.extend(["| Path | Kind | Freshness | Sections | Warnings |", "|---|---|---|---|---|"])
    for item in audit.repo_files:
        lines.append(
            f"| `{item.path}` | {item.kind} | {item.freshness} | {display_list(item.sections)} | "
            f"{display_list(item.warnings)} |"
        )
    lines.append("")
    return lines


def render_archive_section(audit: HandoffAudit) -> list[str]:
    lines = ["## Archive Handoff Signals", ""]
    if not audit.archive_index_present:
        return lines + ["- `archive/index.jsonl` is missing; archive handoff coverage was not scanned.", ""]
    if not audit.archive_hits:
        return lines + ["- No archive handoff candidates found in scanned records.", ""]
    source_counts = Counter(hit.source for hit in audit.archive_hits)
    lines.extend(["### By Source", ""])
    for source, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{source}`: `{count}`")
    lines.extend(["", "### Samples", ""])
    lines.extend(["| Markdown | Source | Session | Sections | Signals | Warnings |", "|---|---|---|---|---|---|"])
    for hit in audit.archive_hits[:20]:
        lines.append(
            f"| `{hit.markdown_path}` | `{hit.source}` | {code_or_dash(hit.session_id)} | "
            f"{display_list(hit.sections)} | {display_list(hit.signals)} | {display_list(hit.warnings)} |"
        )
    if len(audit.archive_hits) > 20:
        lines.append(f"| ... | ... | ... | ... | ... | `{len(audit.archive_hits) - 20} more` |")
    lines.append("")
    return lines


def render_gaps_section(audit: HandoffAudit) -> list[str]:
    lines = ["## Gaps And Follow-Ups", ""]
    if not audit.missing_expected_paths and not any(item.warnings for item in audit.repo_files):
        lines.append("- No repo handoff gaps detected by this report-only audit.")
    else:
        for missing_path in audit.missing_expected_paths:
            lines.append(f"- Missing: {missing_path}.")
        for repo_file in audit.repo_files:
            for warning in repo_file.warnings:
                lines.append(f"- `{repo_file.path}`: {warning}.")
    lines.extend(
        [
            "- K6 will own persistent normalized records in `baseline/handoffs/index.jsonl`.",
            "- K7 will own handoff-derived proposal generation with structured trace records.",
            "",
        ]
    )
    return lines


def display_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "-"


def code_or_dash(value: str | None) -> str:
    return f"`{value}`" if value else "-"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"
