"""Archive export, discovery, and index operations."""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import ArchiveConfig
from .models import Source
from .render import markdown_for_session, write_pdf
from .sources.registry import get_extractor
from .utils import now_utc, read_jsonl_dicts, slugify


IMPORTED_AT_RE = re.compile(r"^- Imported at: `([^`]+)`$", re.MULTILINE)
GENERATED_RE = re.compile(r"^Generated: `([^`]+)`$", re.MULTILINE)


@dataclass(frozen=True)
class ExportResult:
    exported: int
    pdf_missing: bool = False
    skipped_sources: tuple[str, ...] = ()


def iter_source_files(source: Source) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in source.roots:
        if not root.exists():
            continue
        for path in root.glob(source.glob):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_raw(config: ArchiveConfig, path: Path, source: Source, digest: str) -> Path:
    raw_target = config.raw_dir / source.name / f"{digest[:16]}-{path.name}.gz"
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    with path.open("rb") as src, gzip.open(raw_target, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return raw_target


def select_sources(config: ArchiveConfig, selected: list[str] | None) -> list[Source]:
    if not selected:
        return list(config.sources)
    wanted = set(selected)
    known = {source.name for source in config.sources} | {source.kind for source in config.sources}
    for selector in sorted(wanted - known):
        print(f"warning: --source {selector!r} matched no configured source name or kind.", file=sys.stderr)
    return [source for source in config.sources if source.name in wanted or source.kind in wanted]


def _index_path_exists(config: ArchiveConfig, rel: Any) -> bool:
    return isinstance(rel, str) and bool(rel) and (config.repo_root / rel.replace("\\", "/")).exists()


def _can_reuse_record(
    config: ArchiveConfig,
    prior: dict[str, Any] | None,
    size: int,
    mtime: float,
    write_pdfs: bool,
    copy_raw_files: bool,
) -> bool:
    """Skip re-hashing/re-extracting a source file that is unchanged since the
    last export (matching size + mtime) as long as the outputs it would produce
    already exist on disk. Records written before TD15 lack size/mtime and never
    match, so they fall through to a full re-export.

    Tradeoff: identity is (size, mtime), not a content hash — a same-size,
    same-mtime in-place edit (unusual for append-only agent logs) would be
    missed. Run `export` after touching a file, or `prune`/re-export, to force a
    fresh hash if that ever matters."""
    if prior is None or prior.get("size") != size or prior.get("mtime") != mtime:
        return False
    if not _index_path_exists(config, prior.get("markdown")):
        return False
    if write_pdfs and not _index_path_exists(config, prior.get("pdf")):
        return False
    if copy_raw_files and not _index_path_exists(config, prior.get("raw")):
        return False
    return True


def export_sources(
    config: ArchiveConfig,
    selected: list[str] | None = None,
    limit: int | None = None,
    write_pdfs: bool = False,
    copy_raw_files: bool = False,
    dry_run: bool = False,
) -> ExportResult:
    sources = select_sources(config, selected)
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    existing_records = read_existing_index_records(config)
    prior_by_key = {} if dry_run else {index_record_key(record): record for record in existing_records}
    records: list[dict[str, Any]] = []
    pdf_missing = False
    skipped_sources: list[str] = []
    exported = 0

    for source in sources:
        extractor = get_extractor(source.kind)
        if extractor is None:
            skipped_sources.append(f"{source.name} ({source.kind})")
            continue
        for root in source.roots:
            if "__missing_" in str(root):
                print(
                    f"warning: source {source.name!r} has an unresolved path template "
                    f"({root}); skipping that root. Set it in sources.toml if this machine has it.",
                    file=sys.stderr,
                )
        for path in iter_source_files(source):
            if limit and exported >= limit:
                break
            stat_result = path.stat()
            size, mtime = stat_result.st_size, stat_result.st_mtime
            prior = prior_by_key.get((source.name, str(path)))
            if _can_reuse_record(config, prior, size, mtime, write_pdfs, copy_raw_files):
                assert prior is not None  # _can_reuse_record returns False for None
                records.append(prior)  # unchanged since last export: skip hashing/extraction/render
                exported += 1
                continue
            digest = sha256_file(path)
            session = extractor(path)
            session_id = str(session.metadata.get("session_id") or path.stem)
            changed = source_modified_date(path)
            stem = slugify(f"{changed}-{session_id}-{path.stem}-{digest[:12]}")
            out_dir = config.archive_dir / source.name
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / f"{stem}.md"
            markdown = markdown_for_session(source, path, session, digest, imported_at=existing_imported_at(md_path))
            md_changed = True
            if not dry_run:
                md_changed = write_text_if_changed(md_path, markdown)
            pdf_path = None
            if write_pdfs:
                pdf_path = md_path.with_suffix(".pdf")
                should_write_pdf = md_changed or not pdf_path.exists()
                if not dry_run and should_write_pdf and not write_pdf(markdown, pdf_path):
                    pdf_missing = True
                    pdf_path = None
            raw_path = None
            if copy_raw_files and not dry_run:
                raw_path = copy_raw(config, path, source, digest)
            records.append(
                {
                    "source": source.name,
                    "kind": source.kind,
                    "source_file": str(path),
                    "sha256": digest,
                    "size": size,
                    "mtime": mtime,
                    "messages": len(session.messages),
                    "markdown": as_repo_relative(config, md_path),
                    "pdf": as_repo_relative(config, pdf_path) if pdf_path else None,
                    "raw": as_repo_relative(config, raw_path) if raw_path else None,
                    "metadata": session.metadata,
                }
            )
            exported += 1
        if limit and exported >= limit:
            break

    if not dry_run:
        write_indexes(config, merge_index_records(existing_records, records))
    return ExportResult(exported=exported, pdf_missing=pdf_missing, skipped_sources=tuple(skipped_sources))


def index_record_key(record: dict[str, Any]) -> tuple[str, str]:
    # Path identity: used by `status` to match index records against the files
    # visible on THIS machine (keyed by source name + local path).
    return (str(record.get("source", "")), str(record.get("source_file", "")))


def index_identity_key(record: dict[str, Any]) -> tuple[str, ...]:
    # Merge identity: machine-independent so the same logical session exported
    # from Windows and WSL (different absolute source_file paths) collapses to a
    # single record, while a re-export of a changed file still supersedes the old
    # record instead of accumulating. session_id is stable across both machines
    # and content changes; fall back to (source, source_file) when it is absent.
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        session_id = str(metadata.get("session_id", "")).strip()
        if session_id:
            return ("session", session_id)
    return ("path", str(record.get("source", "")), str(record.get("source_file", "")))


def _posix_index_record(record: dict[str, Any]) -> dict[str, Any]:
    # Repo-relative archive paths are written POSIX-normalized once, here, so
    # downstream consumers never have to compensate for OS separators.
    normalized = dict(record)
    for key in ("markdown", "pdf", "raw"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = value.replace("\\", "/")
    return normalized


def read_existing_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    index_path = config.archive_dir / "index.jsonl"
    if not index_path.exists():
        return []
    return read_jsonl_dicts(index_path, label="archive/index.jsonl")


def merge_index_records(existing: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, ...], dict[str, Any]] = {}
    order: list[tuple[str, ...]] = []
    for record in [*existing, *current]:
        key = index_identity_key(record)
        if key not in merged:
            order.append(key)
        merged[key] = record
    return [merged[key] for key in order]


def write_indexes(config: ArchiveConfig, records: list[dict[str, Any]]) -> None:
    records = [_posix_index_record(record) for record in records]
    jsonl_path = config.archive_dir / "index.jsonl"
    jsonl_text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    write_text_if_changed(jsonl_path, jsonl_text)

    lines = [
        "# Agent Session Archive",
        "",
        f"Generated: `{now_utc()}`",
        "",
        "| Source | Kind | Messages | Markdown | PDF |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for record in records:
        md = record["markdown"].replace("\\", "/")
        link = os.path.relpath(config.repo_root / md, config.archive_dir).replace("\\", "/")
        pdf_link = ""
        if record.get("pdf"):
            pdf_norm = record["pdf"].replace("\\", "/")
            pdf_rel = os.path.relpath(config.repo_root / pdf_norm, config.archive_dir).replace("\\", "/")
            pdf_link = f"[PDF]({pdf_rel})"
        lines.append(
            f"| {record['source']} | {record['kind']} | {record['messages']} | "
            f"[{Path(md).name}]({link}) | {pdf_link} |"
        )
    index_path = config.archive_dir / "INDEX.md"
    index_text = preserve_generated_at(index_path, "\n".join(lines) + "\n")
    write_text_if_changed(index_path, index_text)


def existing_imported_at(path: Path) -> str | None:
    if not path.exists():
        return None
    match = IMPORTED_AT_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def preserve_generated_at(path: Path, text: str) -> str:
    if not path.exists():
        return text
    existing = path.read_text(encoding="utf-8", errors="replace")
    if GENERATED_RE.sub("Generated: `<generated>`", existing) != GENERATED_RE.sub("Generated: `<generated>`", text):
        return text
    match = GENERATED_RE.search(existing)
    if not match:
        return text
    return GENERATED_RE.sub(f"Generated: `{match.group(1)}`", text, count=1)


def write_text_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8", errors="replace") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def load_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    index_path = config.archive_dir / "index.jsonl"
    if not index_path.exists():
        raise SystemExit("archive/index.jsonl does not exist. Run export first.")
    return read_jsonl_dicts(index_path, label="archive/index.jsonl")


def prune_index_records(config: ArchiveConfig, dry_run: bool = False) -> int:
    """Drop index records whose archive Markdown file no longer exists on disk.

    Safe GC for entries orphaned when a source file's digest changed (a fresh
    stem/record supersedes the old one) or an archive file was deleted. Records
    from other machines stay put as long as their committed Markdown is present.
    """
    records = read_existing_index_records(config)
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for record in records:
        markdown = record.get("markdown")
        target = config.repo_root / str(markdown).replace("\\", "/") if isinstance(markdown, str) else None
        if target is not None and target.exists():
            kept.append(record)
        else:
            dropped.append(record)
    for record in dropped:
        print(f"prune: dropping stale index record for {record.get('markdown')!r} (missing on disk)")
    if not dropped:
        print("prune: no stale index records found.")
    elif not dry_run:
        write_indexes(config, kept)
        print(f"prune: removed {len(dropped)} record(s); {len(kept)} remain.")
    else:
        print(f"prune: would remove {len(dropped)} record(s); {len(kept)} would remain.")
    return 0


def pdf_existing(
    config: ArchiveConfig,
    selected: list[str] | None = None,
    limit: int | None = None,
    force: bool = False,
) -> int:
    records = load_index_records(config)
    wanted = set(selected or [])
    made = 0
    skipped = 0
    missing_renderer = False

    for record in records:
        if wanted and record.get("source") not in wanted and record.get("kind") not in wanted:
            continue
        if limit and made >= limit:
            break
        md_path = config.repo_root / record["markdown"]
        if not md_path.exists():
            skipped += 1
            continue
        pdf_path = md_path.with_suffix(".pdf")
        if pdf_path.exists() and not force:
            record["pdf"] = as_repo_relative(config, pdf_path)
            skipped += 1
            continue
        markdown = md_path.read_text(encoding="utf-8", errors="replace")
        if not write_pdf(markdown, pdf_path):
            missing_renderer = True
            break
        record["pdf"] = as_repo_relative(config, pdf_path)
        made += 1

    write_indexes(config, records)
    print(f"PDFs written: {made}; skipped: {skipped}.")
    if missing_renderer:
        print("PDF export requires reportlab. Run: python -m pip install reportlab")
        return 1
    return 0


def discover_sources(config: ArchiveConfig, samples: int = 10, write: str | None = None) -> int:
    lines = ["# Agent Session Discovery", "", f"Generated: `{now_utc()}`", ""]
    for source in config.sources:
        lines.extend([f"## {source.name}", "", f"- Kind: `{source.kind}`", f"- Glob: `{source.glob}`"])
        if source.description:
            lines.append(f"- Description: {source.description}")
        total_files = 0
        total_bytes = 0
        for root in source.roots:
            exists = root.exists()
            lines.append(f"- Root: `{root}` ({'exists' if exists else 'missing'})")
            if not exists:
                continue
            files = [p for p in root.glob(source.glob) if p.is_file()]
            total_files += len(files)
            total_bytes += sum(p.stat().st_size for p in files)
        lines.extend([f"- Matching files: `{total_files}`", f"- Matching bytes: `{total_bytes}`", ""])
        sample_count = 0
        for path in iter_source_files(source):
            lines.append(f"  - `{path}` ({path.stat().st_size} bytes)")
            sample_count += 1
            if sample_count >= samples:
                break
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    if write:
        target = Path(write)
        if not target.is_absolute():
            target = config.repo_root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text)
    return 0


def source_modified_date(path: Path) -> str:
    return dt_from_timestamp(path.stat().st_mtime)


def dt_from_timestamp(timestamp: float) -> str:
    # Use UTC so the archive stem is stable regardless of the exporting
    # machine's timezone; render.py records the modified timestamp in UTC too,
    # so a session near midnight (or exported from two timezones) resolves to a
    # single stem and a single archive file.
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y%m%d")


def as_repo_relative(config: ArchiveConfig, path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(config.repo_root))
