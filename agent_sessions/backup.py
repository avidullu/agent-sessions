"""Independent, append-only, content-addressed session backups.

Objects contain original bytes. Immutable JSON snapshots map private source paths
to objects; neither source deletion nor a later run removes previous versions.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import socket
import tempfile
import time
import uuid
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from .archive import iter_source_files
from .config import ArchiveConfig

FORMAT = "agent-sessions-backup-v1"


def destination(config: ArchiveConfig, override: Path | None = None) -> Path:
    value = override or config.backup_dir
    if value is None:
        raise ValueError("Set [backup].directory or --destination to an independent directory.")
    root = value.expanduser().resolve()
    protected = [config.repo_root, config.archive_dir, config.raw_dir]
    protected.extend(p for s in config.sources for p in s.roots)
    if any(root.is_relative_to(p.resolve()) or p.resolve().is_relative_to(root) for p in protected):
        raise ValueError("Backup destination must be outside the checkout, archive, raw, and source directories.")
    return root


def safe_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Backup path escapes destination.")
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("Symlinks are not allowed inside a backup destination.")
    return path


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def initialize(root: Path, compression: str = "gzip") -> None:
    """Explicit initialization only; ordinary runs never recreate a lost mount."""
    if compression not in ("gzip", "none"):
        raise ValueError("Compression must be gzip or none.")
    if not root.parent.is_dir():
        raise ValueError("Destination parent must exist (mount the backup disk first).")
    root.mkdir(mode=0o700, exist_ok=True)
    marker = safe_path(root, "backup.json")
    if marker.exists():
        require_backup(root)
        if compression_mode(root) != compression:
            raise ValueError("Store already initialized with a different compression mode; use a new directory.")
        return
    if any(root.iterdir()):
        raise ValueError("Initialize an empty dedicated directory.")
    for name in ("objects", "snapshots"):
        (root / name).mkdir(mode=0o700)
    (root / "RECOVERY.txt").write_text(
        "Agent Sessions independent backup\n\n"
        "backup.json names the format and compression (gzip or none).\n"
        "snapshots/*.json maps original paths to SHA-256 objects and uncompressed sizes.\n"
        "objects/XX/SHA256[.gz] contains original bytes (gunzip .gz first).\n"
        "Verify SHA-256 against the decoded bytes, not the compressed file.\n"
        "No agent installation or live source logs are required to read these files.\n\n"
        "With the agent-archive tool installed:\n"
        "  agent-archive backup verify --destination PATH_TO_THIS_DIRECTORY\n"
        "  agent-archive backup restore --destination PATH_TO_THIS_DIRECTORY "
        "--snapshot SNAPSHOT_FILENAME.json --output NEW_DIRECTORY\n"
        "Restore creates numbered files and restore-map.json with their original paths.\n"
        "Do not remove objects or snapshots. Source deletion is never propagated here.\n"
        "This backup does not protect against deletion of this directory or disk failure.\n",
        encoding="utf-8",
    )
    _write_json(marker, {"format": FORMAT, "compression": compression, "created_at": datetime.now(UTC).isoformat()})
    _sync_directory(root.parent)


def require_backup(root: Path) -> None:
    marker = safe_path(root, "backup.json")
    if not marker.is_file():
        raise ValueError("Initialized backup unavailable; mount the disk or run backup init explicitly.")
    if json.loads(marker.read_text(encoding="utf-8")).get("format") != FORMAT:
        raise ValueError("Unsupported backup format.")
    for name in ("objects", "snapshots"):
        if not safe_path(root, name).is_dir():
            raise ValueError(f"Backup directory missing: {name}")


@contextmanager
def writer_lock(root: Path) -> Iterator[None]:
    lock = safe_path(root, ".write.lock")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("Backup writer lock exists. Check for an active writer before removing a stale lock.") from exc
    owned = os.fstat(fd)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(f"{socket.gethostname()} pid={os.getpid()}\n")
            stream.flush()
            yield
    finally:
        # Close before unlinking for Windows, but never delete a replacement
        # created while this writer still held its original descriptor.
        try:
            current = lock.lstat()
            if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                lock.unlink()
        except FileNotFoundError:
            pass


def compression_mode(root: Path) -> str:
    mode = json.loads(safe_path(root, "backup.json").read_text(encoding="utf-8")).get("compression", "none")
    if mode not in ("gzip", "none"):
        raise ValueError("Unsupported compression mode.")
    return str(mode)


@contextmanager
def open_object(path: Path) -> Iterator[BinaryIO | gzip.GzipFile]:
    with (gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")) as stream:
        yield stream


def object_digest_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open_object(path) as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def stable_signature(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def object_path(root: Path, digest: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid object digest in snapshot.")
    suffix = ".gz" if compression_mode(root) == "gzip" else ""
    return safe_path(root, f"objects/{digest[:2]}/{digest}{suffix}")


def store_file(root: Path, path: Path, checked: set[str]) -> tuple[str, int, bool]:
    """Copy a stable version, hashing the actual copied bytes and reading back."""
    for _ in range(3):
        before = path.stat()
        # Repeated backups hash source bytes but avoid recompressing objects
        # already preserved by this or another machine.
        with path.open("rb") as stream:
            existing_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        signature = (before.st_size, before.st_mtime_ns, before.st_ino)
        if stable_signature(path) != signature:
            continue
        existing_path = object_path(root, existing_digest)
        if existing_path.exists():
            if existing_digest not in checked:
                if object_digest_size(existing_path) != (existing_digest, before.st_size):
                    raise ValueError(f"Backup object is corrupt: {existing_digest}")
                checked.add(existing_digest)
            return existing_digest, before.st_size, False
        fd, name = tempfile.mkstemp(dir=safe_path(root, "objects"), prefix=".pending-")
        temporary = Path(name)
        try:
            digest = hashlib.sha256()
            size = 0
            with os.fdopen(fd, "wb") as target, path.open("rb") as source:
                with compressed_writer(target, compression_mode(root)) as encoded:
                    while chunk := source.read(1024 * 1024):
                        encoded.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino
            ) or size != after.st_size:
                continue
            key = digest.hexdigest()
            target_path = object_path(root, key)
            target_path.parent.mkdir(mode=0o700, exist_ok=True)
            created = not target_path.exists()
            if created:
                os.replace(temporary, target_path)
            if key not in checked:
                if object_digest_size(target_path) != (key, size):
                    raise ValueError(f"Backup object is corrupt: {key}")
                checked.add(key)
            return key, size, created
        finally:
            temporary.unlink(missing_ok=True)
    raise ValueError(f"Source kept changing during backup; retry when idle: {path}")


@contextmanager
def compressed_writer(stream: BinaryIO, mode: str) -> Iterator[BinaryIO | gzip.GzipFile]:
    if mode == "gzip":
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0, compresslevel=6) as encoded:
            yield encoded
    else:
        yield stream


def candidates(config: ArchiveConfig) -> Iterator[tuple[Path, str, str]]:
    """Include inventory sources and historical artifacts, even without an extractor."""
    seen: set[Path] = set()
    for source in config.sources:
        for path in iter_source_files(source):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path, "source", source.name
    for category, directory in (("archive", config.archive_dir), ("raw", config.raw_dir)):
        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.resolve() not in seen:
                    seen.add(path.resolve())
                    yield path, category, ""


def backup(config: ArchiveConfig, root: Path, machine: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    require_backup(root)
    root = destination(config, root)
    with writer_lock(root):
        checked: set[str] = set()
        entries = []
        added = 0
        stored_bytes = 0
        for path, category, source in candidates(config):
            digest, size, created = store_file(root, path, checked)
            added += created
            stored_bytes += object_path(root, digest).stat().st_size if created else 0
            entries.append({"path": str(path.absolute()), "category": category, "source": source,
                            "sha256": digest, "bytes": size})
        manifest = {
            "format": FORMAT,
            "created_at": datetime.now(UTC).isoformat(),
            "machine": machine or config.backup_machine or socket.gethostname(),
            "files": entries,
            "unavailable_source_roots": [str(p) for s in config.sources for p in s.roots if not p.is_dir()],
        }
        name = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex}.json"
        # Every object's data is fsynced above. Flush directory entries once per
        # shard, before publishing any manifest that refers to them.
        for prefix in sorted({key[:2] for key in checked}):
            _sync_directory(safe_path(root, f"objects/{prefix}"))
        _sync_directory(safe_path(root, "objects"))
        _write_json(safe_path(root, f"snapshots/{name}"), manifest)
        return {"snapshot": name, "files": len(entries), "new_objects": added,
                "new_object_bytes": stored_bytes, "logical_bytes": sum(e["bytes"] for e in entries),
                "duration_seconds": round(time.monotonic() - started, 3),
                "unavailable_source_roots": manifest["unavailable_source_roots"]}


def read_snapshot(root: Path, name: str) -> dict[str, Any]:
    if not name or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Use a snapshot filename, not a path.")
    try:
        data = json.loads(safe_path(root, f"snapshots/{name}").read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("format") != FORMAT
                or not isinstance(data.get("machine"), str) or not data["machine"]
                or not isinstance(data.get("files"), list)):
            raise ValueError
        for entry in data["files"]:
            if (not isinstance(entry, dict)
                    or not all(isinstance(entry.get(key), str) for key in ("path", "category", "source", "sha256"))
                    or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
                    or type(entry.get("bytes")) is not int or entry["bytes"] < 0):
                raise ValueError
        return data
    except FileNotFoundError as exc:
        raise ValueError(f"Snapshot not found: {name}") from exc
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid snapshot: {name}") from exc


def snapshots(root: Path, *, failures: list[str] | None = None) -> Iterator[tuple[Path, dict[str, Any]]]:
    require_backup(root)
    for path in sorted(safe_path(root, "snapshots").glob("*.json")):
        try:
            data = read_snapshot(root, path.name)
        except ValueError as exc:
            if failures is None:
                raise
            failures.append(str(exc))
            continue
        yield path, data


def verify(root: Path) -> dict[str, Any]:
    checked: dict[str, tuple[str, int] | None] = {}
    failures: set[str] = set()
    snapshot_failures: list[str] = []
    count = 0
    for _, snapshot in snapshots(root, failures=snapshot_failures):
        count += 1
        for entry in snapshot["files"]:
            digest = entry["sha256"]
            if digest not in checked:
                try:
                    checked[digest] = object_digest_size(object_path(root, digest))
                except (OSError, ValueError, EOFError, zlib.error):
                    checked[digest] = None
            if checked[digest] != (digest, entry["bytes"]):
                failures.add(digest)
    failures.update(snapshot_failures)
    return {"snapshots": count + len(snapshot_failures), "objects_checked": len(checked), "failures": sorted(failures),
            "ok": not failures}


def _restore_object(source: Path, target: Path, digest: str, size: int) -> None:
    """Validate the bytes actually copied; remove incomplete output on failure."""
    copied = hashlib.sha256()
    copied_size = 0
    with target.open("xb") as output:
        try:
            with open_object(source) as stream:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
                    copied.update(chunk)
                    copied_size += len(chunk)
            if (copied.hexdigest(), copied_size) != (digest, size):
                raise ValueError("Corrupt backup object.")
            output.flush()
            os.fsync(output.fileno())
        except (OSError, ValueError, EOFError, zlib.error):
            output.close()
            target.unlink(missing_ok=True)
            raise


def restore(root: Path, snapshot_name: str, output: Path) -> int:
    """Restore into a fresh directory, never to original live paths."""
    require_backup(root)
    snapshot = read_snapshot(root, snapshot_name)
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Restore outside the backup directory.")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = []
    failures = []
    for index, entry in enumerate(snapshot["files"]):
        # Numeric names prevent absolute/traversal paths from a foreign machine.
        suffix = Path(entry["path"].replace("\\", "/")).suffix
        if not re.fullmatch(r"\.[A-Za-z0-9]{1,12}", suffix):
            suffix = ""
        name = f"{index:08d}-{entry['sha256'][:12]}{suffix}"
        try:
            _restore_object(object_path(root, entry["sha256"]), output / name, entry["sha256"], entry["bytes"])
        except (OSError, ValueError, EOFError, zlib.error) as exc:
            failures.append({**entry, "error": type(exc).__name__})
            continue
        rows.append({**entry, "restored_file": name})
    _write_json(output / "restore-map.json", {"snapshot": snapshot_name, "files": rows,
                                             "failures": failures, "complete": not failures})
    if failures:
        raise ValueError(f"Restore incomplete: {len(rows)} files restored, {len(failures)} failed; see restore-map.json.")
    return len(rows)
