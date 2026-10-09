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
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .archive_io import SourceChangingError, archive_writer, artifact_stem, capture_source, pending_output
from .catalog import read_catalog, validate_archive_catalog
from .config import ArchiveConfig
from .models import Source
from .portable_paths import portable_metadata, portable_origin, portable_path, portable_record
from .render import markdown_for_session, write_pdf
from .sources.registry import get_extractor
from .utils import now_utc

IMPORTED_AT_RE = re.compile(r"^- Imported at: `([^`]+)`$", re.MULTILINE)
GENERATED_RE = re.compile(r"^Generated: `([^`]+)`$", re.MULTILINE)
ROUTER_INDEX_FILENAME = ".router-index.jsonl"
TAIL_HASH_BYTES = 64 * 1024


@dataclass(frozen=True)
class ExportResult:
    exported: int
    pdf_missing: bool = False
    skipped_sources: tuple[str, ...] = ()
    deferred_files: tuple[str, ...] = ()
    malformed_files: int = 0
    empty_files: int = 0
    unsupported_files: int = 0


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


def tail_sha256_file(path: Path, max_bytes: int = TAIL_HASH_BYTES) -> str:
    h = hashlib.sha256()
    size = path.stat().st_size
    bytes_to_read = min(size, max_bytes)
    with path.open("rb") as f:
        if bytes_to_read:
            f.seek(size - bytes_to_read)
            h.update(f.read(bytes_to_read))
    return h.hexdigest()


def copy_raw(config: ArchiveConfig, path: Path, source: Source, digest: str) -> Path:
    # Leave room for the digest prefix and gzip suffix under filesystem name limits.
    raw_name = path.name.encode()[:235].decode("utf-8", errors="ignore")
    raw_target = config.raw_dir / source.name / f"{digest[:16]}-{raw_name}.gz"
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    with pending_output(raw_target) as pending, path.open("rb") as src, gzip.open(pending, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return raw_target


def select_sources(config: ArchiveConfig, selected: list[str] | None) -> list[Source]:
    if not selected:
        return list(config.sources)
    wanted = set(selected)
    known = {source.name for source in config.sources} | {source.kind for source in config.sources}
    for selector in sorted(wanted - known):
        print(f"warning: --source {selector!r} matched no configured source name or kind.", file=sys.stderr)
    matches = [source for source in config.sources if source.name in wanted or source.kind in wanted]
    if not matches:
        raise ValueError("No configured sources matched --source. Use discover to list available names and kinds.")
    return matches


def _index_path_exists(config: ArchiveConfig, rel: Any) -> bool:
    return isinstance(rel, str) and bool(rel) and (config.repo_root / rel.replace("\\", "/")).is_file()


def _can_reuse_record(
    config: ArchiveConfig,
    prior: dict[str, Any] | None,
    size: int,
    mtime: float,
    write_pdfs: bool,
    copy_raw_files: bool,
    tail_sha256: str | None = None,
) -> bool:
    """Skip re-hashing/re-extracting a source file that is unchanged since the
    last export (matching size + mtime) as long as the outputs it would produce
    already exist on disk. Records written before TD15 lack size/mtime and never
    match, so they fall through to a full re-export.

    Newer records also carry a trailing-byte hash; when present, a same-size,
    same-mtime file is reused only if its current tail still matches."""
    if prior is None or prior.get("size") != size or prior.get("mtime") != mtime:
        return False
    prior_tail = prior.get("tail_sha256")
    if isinstance(prior_tail, str) and prior_tail and tail_sha256 != prior_tail:
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
    # Validate selectors before creating the archive or writer lock.
    select_sources(config, selected)
    if dry_run:
        return _export_sources(config, selected, limit, write_pdfs, copy_raw_files, dry_run)
    validate_archive_catalog(config)
    with archive_writer(config.archive_dir):
        validate_archive_catalog(config)
        return _export_sources(config, selected, limit, write_pdfs, copy_raw_files, dry_run)


def _export_sources(
    config: ArchiveConfig,
    selected: list[str] | None,
    limit: int | None,
    write_pdfs: bool,
    copy_raw_files: bool,
    dry_run: bool,
) -> ExportResult:
    sources = select_sources(config, selected)
    existing_records = read_existing_index_records(config)
    prior_by_key = {key: record for record in existing_records for key in index_record_keys(record)}
    records: list[dict[str, Any]] = []
    pdf_missing = False
    skipped_sources: list[str] = []
    deferred: list[str] = []
    malformed_files = empty_files = unsupported_files = exported = 0

    for source in sources:
        extractor = get_extractor(source.kind)
        if extractor is None:
            skipped_sources.append(f"{source.name} ({source.kind})")
            continue
        for root in source.roots:
            if "__missing_" in str(root):
                print(f"warning: source {source.name!r} has an unresolved path template; skipping that root.",
                      file=sys.stderr)
        for path in iter_source_files(source):
            if limit and exported >= limit:
                break
            try:
                with capture_source(path) as captured:
                    size, mtime = captured.stat.st_size, captured.stat.st_mtime
                    digest = captured.digest
                    prior = prior_by_key.get((source.name, portable_path(str(path))))
                    tail_digest = tail_sha256_file(captured.path)
                    if (prior is not None and prior.get("format_version") == 2 and prior.get("sha256") == digest
                            and _can_reuse_record(config, prior, size, mtime, write_pdfs,
                                                  copy_raw_files, tail_digest)):
                        reused = dict(prior)
                        reused.update(source=source.name, source_file=portable_path(str(path)),
                                      source_origin=portable_origin(str(path)))
                        reused.pop("source_aliases", None)
                        records.append(reused)
                        malformed_files += int(prior.get("malformed_rows", 0) > 0)
                        unsupported_files += int(prior.get("unsupported_rows", 0) > 0)
                        empty_files += int(prior.get("parse_status") == "empty")
                        exported += 1
                        continue
                    session = extractor(captured.path)
                    session_id = str(session.metadata.get("session_id") or path.stem)
                    changed = dt.datetime.fromtimestamp(mtime, dt.UTC).strftime("%Y%m%d")
                    stem = artifact_stem(changed, session_id, path.stem, digest)
                    md_path = config.archive_dir / source.name / f"{stem}.md"
                    expected_title = f"# {source.name} / {session_id}"
                    for naming_attempt in range(2):
                        if not md_path.exists():
                            break
                        previous = md_path.read_text(encoding="utf-8", errors="replace")
                        previous_digest = re.search(r"^- SHA-256: `([0-9a-f]{64})`$", previous, re.MULTILINE)
                        if previous_digest is None:
                            raise ValueError("Existing artifact has no valid source binding; its content was preserved.")
                        if previous_digest.group(1) != digest:
                            raise ValueError("Artifact filename conflict; existing content was preserved.")
                        if previous.splitlines()[0] == expected_title:
                            break
                        if naming_attempt:
                            raise ValueError("Artifact identity conflict; existing content was preserved.")
                        stem = artifact_stem(changed, session_id, path.stem, digest, force_identity=True)
                        md_path = config.archive_dir / source.name / f"{stem}.md"
                    markdown = markdown_for_session(
                        source, path, session, digest, imported_at=existing_imported_at(md_path),
                        source_modified=dt.datetime.fromtimestamp(mtime, dt.UTC).isoformat(timespec="seconds"),
                    )
                    md_changed = True
                    if not dry_run:
                        md_changed = write_text_if_changed(md_path, markdown)
                    pdf_path = None
                    if write_pdfs:
                        pdf_path = md_path.with_suffix(".pdf")
                        if not dry_run and (md_changed or not pdf_path.exists()):
                            with pending_output(pdf_path) as pending:
                                if not write_pdf(markdown, pending):
                                    pending.unlink()
                                    pdf_missing = True
                                    pdf_path = None
                    raw_path = None
                    if copy_raw_files and not dry_run:
                        raw_path = copy_raw(config, captured.path, source, digest)
                    malformed_files += int(session.malformed_rows > 0)
                    unsupported_files += int(session.unsupported_rows > 0)
                    empty_files += int(not session.messages)
                    records.append({
                        "format_version": 2, "source": source.name, "kind": source.kind,
                        "source_file": portable_path(str(path)), "source_origin": portable_origin(str(path)),
                        "sha256": digest, "tail_sha256": tail_digest, "size": size, "mtime": mtime,
                        "messages": len(session.messages), "exported_at": now_utc(),
                        "markdown": as_repo_relative(config, md_path),
                        "pdf": as_repo_relative(config, pdf_path) if pdf_path else None,
                        "raw": as_repo_relative(config, raw_path) if raw_path else None,
                        "metadata": portable_metadata(session.metadata),
                        "parse_status": "partial" if session.malformed_rows or session.unsupported_rows else "complete" if session.messages else "empty",
                        "malformed_rows": session.malformed_rows, "input_records": session.input_records,
                        "unsupported_rows": session.unsupported_rows,
                        "empty_reason": ("unsupported_schema" if session.unsupported_rows else
                                         "metadata_only" if session.input_records and session.metadata_records == session.input_records else
                                         "no_transcript") if not session.messages else None,
                    })
                    exported += 1
            except (OSError, SourceChangingError) as exc:
                reason = "changing_source" if isinstance(exc, SourceChangingError) else "source_or_output_unavailable"
                deferred.append(f"{source.name}: {reason}")
                print(f"warning: {source.name!r} capture deferred ({reason}).", file=sys.stderr)
        if limit and exported >= limit:
            break

    if not dry_run:
        router_records = read_router_index_records(config)
        if router_records:
            records = merge_index_records(records, router_records)
        write_indexes(config, merge_index_records(existing_records, records))
    return ExportResult(exported, pdf_missing, tuple(skipped_sources), tuple(deferred),
                        malformed_files, empty_files, unsupported_files)


def index_record_key(record: dict[str, Any]) -> tuple[str, str]:
    # Path identity: used by `status` to match index records against the files
    # visible on THIS machine (keyed by source name + local path). The portable
    # form keeps pre-convention records (absolute paths) comparable with
    # normalized ones.
    return (str(record.get("source", "")), portable_path(str(record.get("source_file", ""))))


def index_record_keys(record: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """All portable path references for a deduplicated content record."""
    return tuple(dict.fromkeys(index_record_key(alias) for alias in [record, *record.get("source_aliases", [])]))


def index_identity_key(record: dict[str, Any]) -> tuple[str, ...]:
    # Merge identity: machine-independent for the same logical content exported
    # from Windows and WSL (different absolute source_file paths), but not so
    # broad that sibling/subagent files sharing a parent session id collapse into
    # one record. The source path upsert in merge_index_records handles changed
    # files from the same machine.
    metadata = record.get("metadata")
    digest = str(record.get("sha256", "")).strip()
    if isinstance(metadata, dict):
        session_id = str(metadata.get("session_id", "")).strip()
        if session_id and digest:
            return ("session", session_id, digest)
    return ("path", str(record.get("source", "")), portable_path(str(record.get("source_file", ""))))


def _posix_index_record(record: dict[str, Any]) -> dict[str, Any]:
    # Repo-relative archive paths are written POSIX-normalized once, here, so
    # downstream consumers never have to compensate for OS separators.
    normalized = _portable_catalog_record(record)
    for key in ("markdown", "pdf", "raw"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = value.replace("\\", "/")
    return normalized


def read_existing_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    index_path = config.archive_dir / "index.jsonl"
    if not index_path.exists():
        return []
    # Normalize on load so indexes written before the portable-path convention
    # are upgraded transparently on the next export/status run.
    return [_portable_catalog_record(record) for record in read_catalog(index_path, warn=True).records]


def _portable_catalog_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = portable_record(record)
    if "source_aliases" in record:
        normalized["source_aliases"] = [portable_record(alias) for alias in record["source_aliases"]]
    return normalized


def read_router_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    """Read records produced by the agent-session-router VS Code extension.

    The extension writes ``archive/.router-index.jsonl`` alongside its rendered
    Markdown files. This function reads those records so they can be merged into
    the main ``archive/index.jsonl`` without requiring a full re-extraction.

    Keeps valid rows when other rows are malformed; writes must validate first.
    """
    router_index_path = config.archive_dir / ROUTER_INDEX_FILENAME
    if not router_index_path.exists():
        return []
    return [_portable_catalog_record(record) for record in read_catalog(router_index_path, warn=True).records]


def merge_index_records(existing: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Upsert paths first, before deduplicating content. Persist alternate path
    # references so a later call can supersede one alias without erasing another.
    by_path: dict[tuple[str, str], dict[str, Any]] = {}
    for record in [*existing, *current]:
        primary = dict(record)
        primary.pop("source_aliases", None)
        for alias in record.get("source_aliases", []):
            alternate = dict(primary)
            alternate.pop("source_origin", None)
            alternate.update(alias)
            # Carried aliases are references, not new observations. A cached
            # row must not overwrite another path's explicit changed record.
            by_path.setdefault(index_record_key(alternate), alternate)
        by_path[index_record_key(primary)] = primary
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for record in by_path.values():
        groups.setdefault(index_identity_key(record), []).append(record)
    merged = []
    for aliases in groups.values():
        primary = dict(aliases[-1])
        if len(aliases) > 1:
            primary["source_aliases"] = [
                {key: alias[key] for key in ("source", "source_file", "source_origin") if key in alias}
                for alias in aliases[:-1]
            ]
        merged.append(primary)
    return merged


def write_indexes(config: ArchiveConfig, records: list[dict[str, Any]]) -> None:
    records = [_posix_index_record(record) for record in records]
    jsonl_path = config.archive_dir / "index.jsonl"
    jsonl_text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)

    lines = [
        "# Agent Session Archive",
        "",
        f"Generated: `{now_utc()}`",
        "",
        "| Source | Kind | Messages | Markdown artifact | PDF artifact |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for record in records:
        md = record["markdown"].replace("\\", "/")
        markdown_cell = f"`{md}`"
        if config.track_artifacts:
            link = os.path.relpath(config.repo_root / md, config.archive_dir).replace("\\", "/")
            markdown_cell = f"[{Path(md).name}]({link})"
        pdf_cell = ""
        if record.get("pdf"):
            pdf_norm = record["pdf"].replace("\\", "/")
            pdf_cell = f"`{pdf_norm}`"
            if config.track_artifacts:
                pdf_rel = os.path.relpath(config.repo_root / pdf_norm, config.archive_dir).replace("\\", "/")
                pdf_cell = f"[PDF]({pdf_rel})"
        lines.append(
            f"| {record['source']} | {record['kind']} | {record.get('messages', 'unknown')} | "
            f"{markdown_cell} | {pdf_cell} |"
        )
    index_path = config.archive_dir / "INDEX.md"
    index_text = preserve_generated_at(index_path, "\n".join(lines) + "\n")
    write_text_if_changed(jsonl_path, jsonl_text)
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
    with pending_output(path) as pending:
        pending.write_text(text, encoding="utf-8", newline="\n")
    return True


def load_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    index_path = config.archive_dir / "index.jsonl"
    if not index_path.exists():
        raise SystemExit("archive/index.jsonl does not exist. Run export first.")
    return [_portable_catalog_record(record) for record in read_catalog(index_path, warn=True).records]


def prune_index_records(config: ArchiveConfig, dry_run: bool = False) -> int:
    if dry_run or not config.track_artifacts:
        return _prune_index_records(config, dry_run)
    validate_archive_catalog(config)
    with archive_writer(config.archive_dir):
        validate_archive_catalog(config)
        return _prune_index_records(config, dry_run)


def _prune_index_records(config: ArchiveConfig, dry_run: bool = False) -> int:
    """Drop index records whose tracked archive Markdown no longer exists.

    Safe GC for artifact-tracking exports where a source file's digest changed
    (a fresh stem/record supersedes the old one) or an archive file was deleted.
    When rendered artifacts are local-only, missing Markdown is not treated as a
    stale record signal.
    """
    if not config.track_artifacts:
        print("prune: archive artifacts are local-only; missing Markdown files are not stale.")
        print(
            "prune: no index records pruned. "
            "Set [archive] track_artifacts = true to prune by artifact presence."
        )
        return 0
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
    validate_archive_catalog(config)
    with archive_writer(config.archive_dir):
        validate_archive_catalog(config)
        return _pdf_existing(config, selected, limit, force)


def _pdf_existing(config: ArchiveConfig, selected: list[str] | None, limit: int | None, force: bool) -> int:
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
        md_path = (config.repo_root / record["markdown"].replace("\\", "/")).resolve()
        if not md_path.is_relative_to(config.archive_dir.resolve()):
            raise ValueError("Catalog Markdown path escapes the configured archive; existing files were preserved.")
        if not md_path.is_file():
            skipped += 1
            continue
        pdf_path = md_path.with_suffix(".pdf")
        if pdf_path.exists() and not force:
            record["pdf"] = as_repo_relative(config, pdf_path)
            skipped += 1
            continue
        markdown = md_path.read_text(encoding="utf-8", errors="replace")
        with pending_output(pdf_path) as pending:
            if not write_pdf(markdown, pending):
                pending.unlink()
                missing_renderer = True
        if missing_renderer:
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
            # docs/DISCOVERY.md is tracked: keep real home prefixes out of it.
            lines.append(f"- Root: `{portable_path(str(root))}` ({'exists' if exists else 'missing'})")
            if not exists:
                continue
            files = [p for p in root.glob(source.glob) if p.is_file()]
            total_files += len(files)
            total_bytes += sum(p.stat().st_size for p in files)
        lines.extend([f"- Matching files: `{total_files}`", f"- Matching bytes: `{total_bytes}`", ""])
        sample_count = 0
        for path in iter_source_files(source):
            lines.append(f"  - `{portable_path(str(path))}` ({path.stat().st_size} bytes)")
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
    return dt.datetime.fromtimestamp(timestamp, dt.UTC).strftime("%Y%m%d")


def as_repo_relative(config: ArchiveConfig, path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(config.repo_root))
