"""Local archive transactions and stable, bounded source snapshots."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


class SourceChangingError(ValueError):
    """A bounded capture could not observe one stable source version."""


@dataclass(frozen=True)
class CapturedSource:
    path: Path
    digest: str
    stat: os.stat_result


def signature(stat: os.stat_result) -> tuple[int, int, int, int]:
    # On Windows path stat reports creation ctime while fstat reports change
    # ctime. Birth time has consistent semantics across both APIs.
    timestamp = getattr(stat, "st_birthtime_ns", 0) if os.name == "nt" else stat.st_ctime_ns
    return stat.st_size, stat.st_mtime_ns, timestamp, stat.st_ino


@contextmanager
def capture_source(path: Path, attempts: int = 3) -> Iterator[CapturedSource]:
    """Hash and parse the same copied bytes; preserve provider filename ancestry."""
    with tempfile.TemporaryDirectory(prefix="agent-archive-capture-") as folder:
        staged = Path(folder).joinpath(*(parent.name for parent in reversed(path.parents[:3])), path.name)
        staged.parent.mkdir(parents=True, exist_ok=True)
        captured = None
        for _ in range(attempts):
            before = path.stat()
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as source, staged.open("wb") as output:
                opened = os.fstat(source.fileno())
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
                    size += len(chunk)
                finished = os.fstat(source.fileno())
            after = path.stat()
            if (signature(before) == signature(opened) == signature(finished) == signature(after)
                    and opened.st_ctime_ns == finished.st_ctime_ns and size == after.st_size):
                os.utime(staged, ns=(after.st_atime_ns, after.st_mtime_ns))
                captured = CapturedSource(staged, digest.hexdigest(), after)
                break
        if captured is None:
            raise SourceChangingError("source kept changing during capture")
        yield captured


@contextmanager
def archive_writer(archive: Path) -> Iterator[None]:
    """Serialize CLI mutations, refusing an active/stale lock without removing it."""
    archive.mkdir(parents=True, exist_ok=True)
    lock = archive / ".archive-write.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Archive writer lock exists; check the active writer before recovering a stale lock.") from exc
    held = os.fstat(fd)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(fd)
        try:
            current = lock.lstat()
            if (current.st_dev, current.st_ino) == (held.st_dev, held.st_ino):
                lock.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def pending_output(target: Path) -> Iterator[Path]:
    """Publish one closed artifact atomically; preserve the old file on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", suffix=target.suffix, dir=target.parent)
    os.close(fd)
    pending = Path(name)
    try:
        yield pending
        if pending.exists():
            # Windows _commit requires a writable handle even after writers close.
            with pending.open("rb+") as stream:
                os.fsync(stream.fileno())
            os.replace(pending, target)
            if os.name != "nt":
                fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
    finally:
        pending.unlink(missing_ok=True)


def artifact_stem(date: str, session_id: str, filename: str, digest: str, *, force_identity: bool = False) -> str:
    """Keep v1 short names; reserve content and identity suffixes for long names."""
    from .utils import slugify

    full = f"{date}-{session_id}-{filename}-{digest[:12]}"
    if not force_identity and len(slugify(full, max_len=len(full))) <= 90:
        return slugify(full)
    identity = hashlib.sha256(f"{session_id}\0{filename}".encode()).hexdigest()[:12]
    prefix = slugify(f"{date}-{session_id}-{filename}", max_len=64)
    return f"{prefix}-{identity}-{digest[:12]}"
