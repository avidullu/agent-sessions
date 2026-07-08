"""Handoff audit and persistent handoff index commands."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .baseline_promote import parse_promoted_blocks, render_project_page_block, upsert_project_page_content
from .baseline_settings import load_baseline_settings
from .baseline_types import BaselineSettings
from .config import ArchiveConfig
from .utils import archive_markdown_path, read_jsonl_dicts, slugify


DEFAULT_AUDIT_PATH = Path("baseline/handoffs/audit.md")
HANDOFF_PROPOSAL_PRODUCER = "baseline handoffs proposals"
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
GENERATED_AT_LINE_RE = re.compile(r"^\*\*Generated at:\*\* (?P<generated_at>.+)$", re.MULTILINE)


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
    source_file: str | None
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


@dataclass(frozen=True)
class HandoffIndexRecord:
    id: str
    source_kind: str
    source: str
    source_file: str
    markdown_path: str
    session_id: str
    project_raw: str
    project_slug: str
    sections: tuple[str, ...]
    signals: tuple[str, ...]
    warnings: tuple[str, ...]
    trace: tuple[dict[str, str], ...]


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


def baseline_handoffs_index(
    config: ArchiveConfig,
    output: Path | None = None,
    max_archive_records: int = 0,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    target = output or settings.root / "handoffs" / "index.jsonl"
    if not target.is_absolute():
        target = config.repo_root / target
    current = build_handoff_index_records(config, settings, max_archive_records=max_archive_records)
    existing = load_handoff_index(target)
    records = merge_handoff_records(existing, current)
    index_text = render_handoff_index_jsonl(records)
    page_updates = project_page_updates(settings, records, generated_at=dt.date.today().isoformat())

    if dry_run:
        print(index_text, end="")
        print(f"Would write {target}")
        for path in page_updates:
            print(f"Would write {path}")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(index_text, encoding="utf-8", newline="\n")
    print(f"Wrote {target}")
    for path, content in page_updates.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote {path}")
    return 0


def baseline_handoffs_proposals(
    config: ArchiveConfig,
    index: Path | None = None,
    output_dir: Path | None = None,
    max_records_per_project: int = 5,
    dry_run: bool = False,
) -> int:
    if max_records_per_project <= 0:
        raise SystemExit("--max-records-per-project must be greater than 0.")
    settings = load_baseline_settings(config)
    index_path = index or settings.root / "handoffs" / "index.jsonl"
    if not index_path.is_absolute():
        index_path = config.repo_root / index_path
    if not index_path.exists():
        raise SystemExit(f"Handoff index does not exist: {index_path}. Run `baseline handoffs index` first.")

    proposals_dir = output_dir or settings.root / "proposals"
    if not proposals_dir.is_absolute():
        proposals_dir = config.repo_root / proposals_dir
    records = load_handoff_index(index_path)
    proposals = build_handoff_proposals(
        settings,
        records,
        max_records_per_project=max_records_per_project,
    )

    if dry_run:
        for proposal in proposals:
            print(json.dumps(proposal, indent=2, ensure_ascii=False, sort_keys=True))
            print(f"Would write {proposal_path(proposals_dir, proposal)}")
        print(f"Would write {len(proposals)} handoff proposal(s).")
        return 0

    proposals_dir.mkdir(parents=True, exist_ok=True)
    for proposal in proposals:
        target = proposal_path(proposals_dir, proposal)
        assert_generated_proposal_target(target)
        payload = json.dumps(proposal, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        target.write_text(payload, encoding="utf-8", newline="\n")
        print(f"Wrote {target}")
    return 0


def build_handoff_proposals(
    settings: BaselineSettings,
    records: list[HandoffIndexRecord],
    *,
    max_records_per_project: int = 5,
) -> list[dict[str, Any]]:
    known_projects = known_project_slugs(settings)
    by_project: dict[str, list[HandoffIndexRecord]] = {}
    for record in records:
        if record.project_slug not in known_projects:
            continue
        by_project.setdefault(record.project_slug, []).append(record)
    return [
        handoff_project_proposal(slug, project_records, max_records_per_project=max_records_per_project)
        for slug, project_records in sorted(by_project.items())
    ]


def handoff_project_proposal(
    slug: str,
    records: list[HandoffIndexRecord],
    *,
    max_records_per_project: int = 5,
) -> dict[str, Any]:
    selected = sorted(records, key=lambda record: (record.markdown_path, record.id))[:max_records_per_project]
    total = len(records)
    standard_sections = sorted({section for record in records for section in record.sections})
    signals = sorted({signal for record in records for signal in record.signals})
    warnings = sum(1 for record in records if record.warnings)
    proposal_id = f"handoff.{slug}.handoff-signals"
    evidence = [
        f"baseline/handoffs/index.jsonl contains {total} handoff candidate(s) for project `{slug}`.",
        *(record.markdown_path for record in selected),
    ]
    open_questions = [
        "Which linked handoffs contain durable project guidance rather than transient next steps?",
    ]
    if warnings:
        open_questions.append(
            f"{warnings} indexed handoff candidate(s) lack standard headings; should they be normalized or ignored?"
        )
    return {
        "id": proposal_id,
        "title": f"Review handoff signals for {slug}",
        "scope": f"project:{slug}",
        "category": "docs",
        "risk": "low",
        "confidence": handoff_proposal_confidence(total, standard_sections),
        "approval_mode": "strict",
        "generated_by": HANDOFF_PROPOSAL_PRODUCER,
        "source_kind": "repo-handoff",
        "evidence": evidence,
        "trace": proposal_trace(selected),
        "suggested_baseline_text": handoff_suggested_text(slug, total, standard_sections, signals),
        "open_questions": open_questions,
    }


def handoff_proposal_confidence(total: int, sections: list[str]) -> float:
    confidence = 0.45 + min(total, 10) * 0.03
    if sections:
        confidence += 0.1
    return round(min(confidence, 0.85), 2)


def proposal_trace(records: list[HandoffIndexRecord]) -> list[dict[str, str]]:
    traces: list[dict[str, str]] = []
    for record in records:
        trace = dict(record.trace[0]) if record.trace else {}
        trace["project_slug"] = record.project_slug
        trace["transform"] = HANDOFF_PROPOSAL_PRODUCER
        traces.append(strip_empty_trace(trace))
    return traces


def handoff_suggested_text(
    slug: str,
    total: int,
    sections: list[str],
    signals: list[str],
) -> str:
    section_text = ", ".join(sections) if sections else "handoff signals"
    signal_text = ", ".join(signals[:5]) if signals else "session handoff references"
    return (
        f"Review the {total} indexed handoff candidate(s) for `{slug}` before promoting durable project guidance. "
        f"Prioritize repeated, still-current lessons from {section_text}; use the linked evidence for {signal_text} "
        "and leave transient next steps out of the baseline."
    )


def proposal_path(output_dir: Path, proposal: dict[str, Any]) -> Path:
    return output_dir / f"{proposal['id']}.json"


def assert_generated_proposal_target(path: Path) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Refusing to overwrite non-JSON proposal: {path}") from exc
    if not isinstance(data, dict) or data.get("generated_by") != HANDOFF_PROPOSAL_PRODUCER:
        raise SystemExit(f"Refusing to overwrite non-generated proposal: {path}")


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
        source_file=optional_str(record.get("source_file")),
        markdown_path=markdown.replace("\\", "/"),
        session_id=optional_str(metadata.get("session_id") or metadata.get("id")),
        project_raw=optional_str(metadata.get("project") or metadata.get("cwd")),
        sections=sections,
        signals=signals,
        warnings=warnings,
    )


def build_handoff_index_records(
    config: ArchiveConfig,
    settings: BaselineSettings,
    max_archive_records: int = 0,
) -> list[HandoffIndexRecord]:
    audit = build_handoff_audit(config, max_archive_records=max_archive_records)
    slug_map = project_slug_map(settings, audit.archive_hits)
    return [handoff_index_record(hit, slug_map[hit]) for hit in audit.archive_hits]


def handoff_index_record(hit: ArchiveHandoffHit, project_slug: str) -> HandoffIndexRecord:
    source_file = hit.source_file or ""
    session_id = hit.session_id or ""
    project_raw = hit.project_raw or ""
    record_id = stable_handoff_id(hit)
    trace = {
        "source": hit.source,
        "source_file": source_file,
        "markdown_path": hit.markdown_path,
        "session_id": session_id,
        "project_slug": project_slug,
        "transform": "baseline handoffs index",
    }
    return HandoffIndexRecord(
        id=record_id,
        source_kind="repo-handoff",
        source=hit.source,
        source_file=source_file,
        markdown_path=hit.markdown_path,
        session_id=session_id,
        project_raw=project_raw,
        project_slug=project_slug,
        sections=hit.sections,
        signals=hit.signals,
        warnings=hit.warnings,
        trace=(strip_empty_trace(trace),),
    )


def strip_empty_trace(trace: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in trace.items() if value}


def stable_handoff_id(hit: ArchiveHandoffHit) -> str:
    source_id = hit.session_id or hit.markdown_path
    digest = hashlib.sha256(f"{hit.source}:{source_id}".encode("utf-8")).hexdigest()[:12]
    return f"handoff.{digest}"


def project_slug_map(settings: BaselineSettings, hits: tuple[ArchiveHandoffHit, ...]) -> dict[ArchiveHandoffHit, str]:
    base: dict[ArchiveHandoffHit, str] = {hit: project_slug_for_raw(settings, hit.project_raw) for hit in hits}
    configured_slugs = {pilot.slug for pilot in settings.pilots}
    raw_by_slug: dict[str, set[str]] = {}
    for hit, slug in base.items():
        raw_by_slug.setdefault(slug, set()).add(normalize_project_raw(hit.project_raw or ""))
    collisions = {
        slug
        for slug, raw_values in raw_by_slug.items()
        if slug and slug not in configured_slugs and len(raw_values) > 1
    }
    if not collisions:
        return base
    result: dict[ArchiveHandoffHit, str] = {}
    for hit, slug in base.items():
        if slug not in collisions:
            result[hit] = slug
            continue
        raw = normalize_project_raw(hit.project_raw or hit.markdown_path)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
        result[hit] = f"{slug}-{digest}"
    return result


def project_slug_for_raw(settings: BaselineSettings, raw: str | None) -> str:
    decoded = normalize_project_raw(raw or "")
    basename = project_basename(decoded)
    decoded_slug = slugify(decoded)
    basename_slug = slugify(basename)
    candidates = {decoded_slug, basename_slug}
    substring_matches: list[tuple[int, str]] = []
    for pilot in settings.pilots:
        pilot_aliases = {pilot.slug, *pilot.aliases}
        alias_slugs = {slugify(alias) for alias in pilot_aliases}
        if candidates & alias_slugs:
            return pilot.slug
        for alias in alias_slugs:
            if alias and (alias in basename_slug or alias in decoded_slug):
                substring_matches.append((len(alias), pilot.slug))
    if substring_matches:
        return max(substring_matches)[1]
    return slugify(basename or decoded or "unknown-project")


def normalize_project_raw(raw: str) -> str:
    return unquote(raw).replace("\\", "/").rstrip("/")


def project_basename(raw: str) -> str:
    normalized = raw.rstrip("/")
    if not normalized:
        return ""
    slugged = slugify(normalized)
    if "-projects-" in slugged:
        candidate = slugged.rsplit("-projects-", 1)[1]
        candidate = candidate.split("-claude-worktrees-", 1)[0]
        if candidate:
            return candidate
    return normalized.split("/")[-1]


def handoff_record_to_dict(record: HandoffIndexRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "source_kind": record.source_kind,
        "source": record.source,
        "source_file": record.source_file,
        "markdown_path": record.markdown_path,
        "session_id": record.session_id,
        "project_raw": record.project_raw,
        "project_slug": record.project_slug,
        "sections": list(record.sections),
        "signals": list(record.signals),
        "warnings": list(record.warnings),
        "trace": [dict(item) for item in record.trace],
    }


def handoff_record_from_dict(data: dict[str, Any]) -> HandoffIndexRecord:
    trace = data.get("trace", [])
    trace_items: list[dict[str, str]] = []
    if isinstance(trace, list):
        for item in trace:
            if isinstance(item, dict):
                trace_items.append({str(key): str(value) for key, value in item.items() if value not in (None, "")})
    return HandoffIndexRecord(
        id=str(data.get("id", "")),
        source_kind=str(data.get("source_kind", "repo-handoff")),
        source=str(data.get("source", "")),
        source_file=str(data.get("source_file", "")),
        markdown_path=str(data.get("markdown_path", "")),
        session_id=str(data.get("session_id", "")),
        project_raw=str(data.get("project_raw", "")),
        project_slug=str(data.get("project_slug", "")),
        sections=tuple(str(item) for item in data.get("sections", []) if item),
        signals=tuple(str(item) for item in data.get("signals", []) if item),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
        trace=tuple(trace_items),
    )


def load_handoff_index(path: Path) -> list[HandoffIndexRecord]:
    if not path.exists():
        return []
    return [handoff_record_from_dict(record) for record in read_jsonl_dicts(path, label=str(path))]


def merge_handoff_records(
    existing: list[HandoffIndexRecord],
    current: list[HandoffIndexRecord],
) -> list[HandoffIndexRecord]:
    merged = {record.id: record for record in existing if record.id}
    for record in current:
        merged[record.id] = record
    return sorted(merged.values(), key=lambda record: (record.project_slug, record.markdown_path, record.id))


def render_handoff_index_jsonl(records: list[HandoffIndexRecord]) -> str:
    lines = [
        json.dumps(handoff_record_to_dict(record), ensure_ascii=False, sort_keys=True)
        for record in sorted(records, key=lambda record: (record.project_slug, record.markdown_path, record.id))
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def project_page_updates(
    settings: BaselineSettings,
    records: list[HandoffIndexRecord],
    *,
    generated_at: str,
) -> dict[Path, str]:
    by_project: dict[str, list[HandoffIndexRecord]] = {}
    for record in records:
        by_project.setdefault(record.project_slug, []).append(record)
    known_projects = known_project_slugs(settings)
    updates: dict[Path, str] = {}
    for slug, project_records in sorted(by_project.items()):
        if slug not in known_projects:
            continue
        page = settings.root / "projects" / slug / "README.md"
        existing = page.read_text(encoding="utf-8") if page.exists() else ""
        block = render_project_handoff_feed(slug, project_records, generated_at=generated_at)
        block = preserve_generated_at_when_feed_unchanged(existing, block, block_id="handoffs.index")
        updates[page] = upsert_project_page_content(existing, {"handoffs.index": block}, slug)
    return updates


def preserve_generated_at_when_feed_unchanged(existing: str, block: str, *, block_id: str) -> str:
    existing_block = parse_promoted_blocks(existing).get(block_id)
    if not existing_block:
        return block
    match = GENERATED_AT_LINE_RE.search(existing_block)
    if not match:
        return block
    if strip_generated_at_line(existing_block) != strip_generated_at_line(block):
        return block
    existing_generated_at = match.group("generated_at")
    return GENERATED_AT_LINE_RE.sub(f"**Generated at:** {existing_generated_at}", block, count=1)


def strip_generated_at_line(block: str) -> str:
    return GENERATED_AT_LINE_RE.sub("**Generated at:** <stable>", block, count=1)


def known_project_slugs(settings: BaselineSettings) -> set[str]:
    configured = {pilot.slug for pilot in settings.pilots}
    existing = {
        path.parent.name
        for path in (settings.root / "projects").glob("*/README.md")
        if path.parent.name
    }
    return configured | existing


def render_project_handoff_feed(
    slug: str,
    records: list[HandoffIndexRecord],
    *,
    generated_at: str,
) -> str:
    sorted_records = sorted(records, key=lambda record: (record.markdown_path, record.id))
    lines = [f"Indexed handoff candidates: `{len(sorted_records)}`.", "", "### Candidates"]
    for record in sorted_records[:10]:
        session = f" session `{record.session_id}`" if record.session_id else ""
        sections = display_list(record.sections)
        lines.append(
            f"- [{record.markdown_path}](../../../{record.markdown_path}){session}; sections: {sections}."
        )
    if len(sorted_records) > 10:
        lines.append(f"- `{len(sorted_records) - 10}` more indexed handoff candidate(s).")
    traces = [record.trace[0] for record in sorted_records[:10] if record.trace]
    return render_project_page_block(
        "handoffs.index",
        "Handoff Signals",
        "\n".join(lines),
        generated_by="baseline handoffs index",
        generated_at=generated_at,
        traces=traces,
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
        "K6 owns `baseline/handoffs/index.jsonl` and project-page feeds; K7 owns proposal writes.",
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
            "- Persistent normalized records live in `baseline/handoffs/index.jsonl`.",
            "- Handoff-derived proposal generation is implemented by `baseline handoffs proposals` with structured trace records.",
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
