"""Schema-aware catalog inspection and fail-closed validation before writes."""

from __future__ import annotations

import json
import math
import sys
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ArchiveConfig

CATALOG_NAMES = ("index.jsonl", ".router-index.jsonl")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def catalog_record_error(record: Any) -> str | None:
    """Check fields needed by readers/writers; newer metadata remains optional.

    Legacy records need not have message counts, fingerprints, timestamps, or
    session metadata. If present, those fields must have their declared types.
    Digest length is not enforced so historical feeder records remain readable.
    """
    if not isinstance(record, dict):
        return "expected a catalog object"
    for name in ("source", "kind", "source_file", "markdown"):
        if name not in record:
            return f"missing required field {name!r}"
        if not _text(record[name]):
            return f"{name!r} must be a nonempty string"
    for name in ("messages", "size", "malformed_rows", "unsupported_rows", "input_records", "mtime_ns", "ctime_ns", "inode"):
        if name in record:
            value = record[name]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return f"{name!r} must be a nonnegative integer"
    if "mtime" in record:
        value = record["mtime"]
        try:
            finite_number = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        except OverflowError:
            finite_number = False
        if not finite_number:
            return "'mtime' must be a finite number"
    for name in ("sha256", "tail_sha256", "exported_at", "source_origin"):
        if name in record and not _text(record[name]):
            return f"{name!r} must be a nonempty string"
    for name in ("pdf", "raw"):
        if name in record and record[name] is not None and not _text(record[name]):
            return f"{name!r} must be a path string or null"
    for name in ("metadata",):
        if name in record and not isinstance(record[name], dict):
            return f"{name!r} must be an object"
    if "parse_status" in record and record["parse_status"] not in ("complete", "partial", "empty"):
        return "'parse_status' must be complete, partial, or empty"
    if record.get("empty_reason") not in (None, "unsupported_schema", "metadata_only", "no_transcript"):
        return "'empty_reason' must describe an empty or unsupported input"
    if "source_aliases" in record:
        aliases = record["source_aliases"]
        if not isinstance(aliases, list):
            return "'source_aliases' must be a list"
        for alias in aliases:
            if not isinstance(alias, dict) or not all(_text(alias.get(name)) for name in ("source", "source_file")):
                return "each source alias must have nonempty source/source_file strings"
            if "source_origin" in alias and not _text(alias["source_origin"]):
                return "alias 'source_origin' must be a nonempty string"
    return None


@dataclass
class CatalogRead:
    records: list[dict[str, Any]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    unreadable: bool = False
    missing: bool = False
    encoding_errors: int = 0
    invalid_rows: int = 0

    @property
    def state(self) -> str:
        if self.unreadable:
            return "unreadable"
        if self.problems:
            return "malformed"
        return "missing" if self.missing else "readable"


def parse_catalog_lines(lines: Iterable[bytes], label: str) -> CatalogRead:
    result = CatalogRead()
    iterator = iter(lines)
    number = 0
    while True:
        try:
            raw = next(iterator)
        except StopIteration:
            break
        except (OSError, EOFError, zlib.error) as exc:
            result.unreadable = True
            result.problems.append(f"{label}: unreadable ({type(exc).__name__})")
            break
        number += 1
        if not raw.strip():
            continue
        try:
            record = json.loads(raw.decode("utf-8"))
        except UnicodeError:
            result.encoding_errors += 1
            result.invalid_rows += 1
            result.problems.append(f"{label}:{number}: invalid UTF-8")
            continue
        except ValueError:
            result.invalid_rows += 1
            result.problems.append(f"{label}:{number}: malformed JSON")
            continue
        error = catalog_record_error(record)
        if error:
            result.invalid_rows += 1
            result.problems.append(f"{label}:{number}: {error}")
        else:
            result.records.append(record)
    return result


def read_catalog(path: Path, *, warn: bool = False) -> CatalogRead:
    try:
        with path.open("rb") as stream:
            result = parse_catalog_lines(stream, path.name)
    except FileNotFoundError:
        result = CatalogRead(missing=True)
    except OSError as exc:
        result = CatalogRead(unreadable=True, problems=[f"{path.name}: unreadable ({type(exc).__name__})"])
    if warn:
        for problem in result.problems:
            print(f"warning: catalog {problem}; inspection counts are incomplete.", file=sys.stderr)
    return result


def validate_archive_catalog(config: ArchiveConfig) -> None:
    """Refuse a rewrite if either catalog is damaged; never alter original bytes.

    Writers must call this while holding their archive transaction lock, before
    creating artifacts or replacing catalogs. A missing catalog is valid.
    """
    problems = [problem for name in CATALOG_NAMES
                for problem in read_catalog(config.archive_dir / name).problems]
    if problems:
        raise ValueError("Cannot modify damaged archive catalogs: " + "; ".join(problems)
                         + ". Original bytes are preserved. Preserve a recovery copy before explicit repair.")
