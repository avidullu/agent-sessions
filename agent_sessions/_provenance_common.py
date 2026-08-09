"""Shared validation and private-file primitives for provenance indexing."""

from __future__ import annotations

import base64
import json
import os
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

MAX_TEXT = 1000

WINDOWS_ACL_PROBE = """
$ErrorActionPreference = 'Stop'
$acl = Get-Acl -LiteralPath $env:AGENT_SESSIONS_PRIVATE_PATH
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$owner = ([System.Security.Principal.NTAccount]$acl.Owner).Translate(
    [System.Security.Principal.SecurityIdentifier]
).Value
$ownerCandidates = @(
    $current,
    'S-1-5-18',
    'S-1-5-32-544'
)
if ($ownerCandidates -notcontains $owner) {
    exit 4
}
$trusted = $ownerCandidates + @('S-1-3-0', 'S-1-3-4')
$unexpected = @()
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) {
        continue
    }
    $sid = $rule.IdentityReference.Translate(
        [System.Security.Principal.SecurityIdentifier]
    ).Value
    if ($trusted -notcontains $sid) {
        $unexpected += $sid
    }
}
if ($unexpected.Count -ne 0) {
    exit 3
}
"""

WINDOWS_ACL_HARDEN = """
$ErrorActionPreference = 'Stop'
$path = $env:AGENT_SESSIONS_PRIVATE_PATH
$item = Get-Item -LiteralPath $path -Force
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$rights = if ($item.PSIsContainer) { '(OI)(CI)F' } else { 'F' }
$arguments = @(
    $path,
    '/inheritance:r',
    '/grant:r',
    "*$current`:$rights",
    "*S-1-5-18`:$rights",
    "*S-1-5-32-544`:$rights",
    '/q'
)
& icacls.exe @arguments | Out-Null
if ($LASTEXITCODE -ne 0) {
    exit 5
}
"""


class ProvenanceError(RuntimeError):
    """A database, policy, API, or attribution invariant failed."""


def _fail(message: str) -> NoReturn:
    raise ProvenanceError(message)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bounded(value: Any, field: str, *, maximum: int = MAX_TEXT, allow_empty: bool = True) -> str:
    if value is None and allow_empty:
        return ""
    if not isinstance(value, str) or "\0" in value or len(value) > maximum:
        raise ProvenanceError(f"{field} must be a string of at most {maximum} characters")
    if not allow_empty and not value.strip():
        raise ProvenanceError(f"{field} must not be empty")
    return value


def _one_line(value: Any, field: str, *, maximum: int = MAX_TEXT, allow_empty: bool = True) -> str:
    result = _bounded(value, field, maximum=maximum, allow_empty=allow_empty)
    if "\n" in result or "\r" in result:
        raise ProvenanceError(f"{field} must be one line")
    return result


def _positive_integer(value: Any, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ProvenanceError(f"{field} must be a positive integer")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ProvenanceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _json(raw: bytes, description: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_pairs,
            parse_constant=lambda token: _fail(f"non-finite JSON value in {description}: {token}"),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"invalid JSON in {description}: {exc}") from exc


def _same_file(path: Path, opened: os.stat_result, description: str) -> None:
    try:
        current = path.lstat()
    except OSError as exc:
        raise ProvenanceError(f"cannot stat {path}: {exc}") from exc
    if stat.S_ISLNK(current.st_mode) or not stat.S_ISREG(current.st_mode):
        raise ProvenanceError(f"expected a regular non-symlink file: {path}")
    if not os.path.samestat(opened, current):
        raise ProvenanceError(f"{description} changed while it was open: {path}")


def _read_regular(path: Path, *, maximum: int, secret: bool = False) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ProvenanceError(f"cannot open regular non-symlink file {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ProvenanceError(f"expected a regular non-symlink file: {path}")
        if before.st_size > maximum:
            raise ProvenanceError(f"file exceeds {maximum} bytes: {path}")
        _same_file(path, before, "file")
        if secret:
            _require_private_access(path, before)
            _same_file(path, before, "secret file")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(raw) > maximum:
            raise ProvenanceError(f"file exceeds {maximum} bytes: {path}")
        if (
            not os.path.samestat(before, after)
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or len(raw) != after.st_size
        ):
            raise ProvenanceError(f"file changed while reading: {path}")
        _same_file(path, after, "file")
        return raw
    except OSError as exc:
        raise ProvenanceError(f"cannot read {path}: {exc}") from exc
    finally:
        os.close(descriptor)


def _require_private_access(path: Path, info: os.stat_result | None = None) -> None:
    """Require POSIX owner-only bits or a Windows ACL without broad readers."""
    observed = info if info is not None else path.lstat()
    if os.name != "nt":
        if stat.S_IMODE(observed.st_mode) & 0o077:
            raise ProvenanceError(f"secret file must not be group/world accessible: {path}")
        return
    environment = os.environ.copy()
    environment["AGENT_SESSIONS_PRIVATE_PATH"] = str(path)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", _powershell_encoded(WINDOWS_ACL_PROBE)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProvenanceError(f"cannot verify the current-user Windows ACL: {path}") from exc
    if result.returncode != 0:
        raise ProvenanceError(f"secret file ACL grants an unexpected Windows principal: {path}")


def _harden_private_access(path: Path) -> None:
    """Replace inherited Windows access with current-user/system/admin rules."""
    if os.name != "nt":
        return
    environment = os.environ.copy()
    environment["AGENT_SESSIONS_PRIVATE_PATH"] = str(path)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", _powershell_encoded(WINDOWS_ACL_HARDEN)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProvenanceError(f"cannot harden the current-user Windows ACL: {path}") from exc
    if result.returncode != 0:
        raise ProvenanceError(f"cannot harden the current-user Windows ACL: {path}")


def _powershell_encoded(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")
