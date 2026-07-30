"""Portable, PII-free forms of user-machine paths for tracked catalog files.

Tracked catalogs (``archive/index.jsonl``, ``baseline/handoffs/index.jsonl``,
``baseline/proposals/*.json``) are committed to the repository, so they must
never carry a real user home directory or username (public-launch DoD,
``docs/archives/PUBLIC_LAUNCH_TRACKER.md`` L1/§9). Paths are stored home-relative
(``~``-prefixed) and the origin environment is captured separately —
username-free — at write time via :func:`portable_origin`.

The transforms are deterministic and idempotent so the same normalization can
be applied to freshly scanned live paths when they are compared against stored
records (export reuse, ``status`` matching). They intentionally match *any*
username, not just the current user's, so records exported on one machine stay
stable when read on another.

Best-effort caveat: encoded Claude project keys (``C--Users-<user>-...``)
assume the username is a single hyphen-free token, matching how short local
usernames are encoded. Hyphenated usernames are only partially normalized —
the same documented limitation as redaction-v1.
"""

from __future__ import annotations

import re
from typing import Any

# Home-directory prefixes, matched against the start of a path. Ordering
# matters: UNC WSL homes must win before the bare-POSIX form, and the
# /mnt/<drive> form before /home. Each rewrite keeps the path tail (and its
# original separators) verbatim so record keys stay stable per machine.
_HOME_PREFIXES = (
    # \\wsl.localhost\Ubuntu\home\user  or  //wsl$/Ubuntu/home/user
    re.compile(r"^[\\/]{2}wsl(?:\.localhost|\$)?[\\/][^\\/]+[\\/]home[\\/][^\\/]+(?=[\\/]|$)"),
    # C:\Users\user  or  C:/Users/user
    re.compile(r"^[A-Za-z]:[\\/]Users[\\/][^\\/]+(?=[\\/]|$)"),
    # /mnt/c/Users/user
    re.compile(r"^/mnt/[A-Za-z]/Users/[^/]+(?=/|$)"),
    # /home/user
    re.compile(r"^/home/[^/]+(?=/|$)"),
    # /Users/user (macOS)
    re.compile(r"^/Users/[^/]+(?=/|$)"),
)

# Encoded home prefixes as they appear inside Claude Code project-directory
# names (path separators flattened to "-"), e.g.
# ``C--Users-alice-Projects-demo`` or ``-home-alice-Projects-demo``. These can
# occur mid-path (the project dir is a path component), so they are replaced
# anywhere in a string — but only in strings that already look like paths.
_ENCODED_HOME_SEGMENTS = (
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]--Users-[A-Za-z0-9_.]+(?=-|[\\/]|$)"),
    re.compile(r"(?<![A-Za-z0-9])-home-[A-Za-z0-9_.]+(?=-|[\\/]|$)"),
    re.compile(r"(?<![A-Za-z0-9])-mnt-[A-Za-z]-Users-[A-Za-z0-9_.]+(?=-|[\\/]|$)"),
)

_PATHISH_RE = re.compile(r"[\\/]|^[A-Za-z]:|^~")

# A value that IS a bare encoded key (e.g. metadata "project":
# "C--Users-alice-Projects-app") has no separators, so the path-ish gate above
# would skip it; a leading encoded-home prefix is treated as path context too.
_ENCODED_START_RE = re.compile(r"^(?:[A-Za-z]--Users-|-home-|-mnt-[A-Za-z]-Users-)")

_WINDOWS_ORIGIN_RE = re.compile(r"^([A-Za-z]):\\Users\\[^\\]+\\", flags=re.IGNORECASE)
_WSL_ORIGIN_RE = re.compile(r"^\\\\wsl(?:\.localhost|\$)?\\([^\\]+)\\home\\[^\\]+\\")
_POSIX_ORIGIN_RE = re.compile(r"^/home/[^/]+/")
_MACOS_ORIGIN_RE = re.compile(r"^/Users/[^/]+/")
_MNT_ORIGIN_RE = re.compile(r"^/mnt/([A-Za-z])/Users/[^/]+/")


def portable_path(value: str) -> str:
    """Rewrite any user home-directory prefix (and encoded home segments) to ``~``.

    Idempotent; strings that carry no home prefix are returned unchanged.
    Separators in the tail are preserved so that per-machine string equality
    (stored record vs. freshly scanned path) survives the rewrite.
    """
    result = value
    for pattern in _HOME_PREFIXES:
        replaced = pattern.sub("~", result)
        if replaced != result:
            result = replaced
            break
    if _PATHISH_RE.search(result) or _ENCODED_START_RE.match(result):
        for pattern in _ENCODED_HOME_SEGMENTS:
            result = pattern.sub("~", result)
    return result


def portable_metadata(value: Any) -> Any:
    """Recursively apply :func:`portable_path` to string values in metadata.

    Session metadata (``cwd``, ``project``, agent-specific fields) is stored
    verbatim in tracked index records, so any absolute user path inside it is
    normalized the same way ``source_file`` is.
    """
    if isinstance(value, str):
        return portable_path(value)
    if isinstance(value, dict):
        return {key: portable_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_metadata(item) for item in value]
    return value


def portable_origin(path: str) -> str:
    """Classify a (pre-normalization) path into a username-free origin key.

    Mirrors ``archive_status.classify_source_origin`` categories but never
    embeds the username, so the result is safe to persist in tracked records.
    """
    normalized = path.replace("/", "\\")
    windows_match = _WINDOWS_ORIGIN_RE.match(normalized)
    if windows_match:
        return f"windows-user:{windows_match.group(1).upper()}"
    wsl_match = _WSL_ORIGIN_RE.match(normalized)
    if wsl_match:
        return f"wsl-user:{wsl_match.group(1)}"
    if _POSIX_ORIGIN_RE.match(path):
        return "posix-home"
    if _MACOS_ORIGIN_RE.match(path):
        return "macos-user"
    mnt_match = _MNT_ORIGIN_RE.match(path)
    if mnt_match:
        return f"wsl-mounted-windows-user:{mnt_match.group(1).upper()}"
    return "unknown"


def portable_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of an index record with portable paths.

    Applied on load so indexes written before this convention (absolute
    ``source_file``, verbatim metadata, no ``source_origin``) are upgraded
    transparently: the origin is classified from the original absolute path
    *before* it is rewritten, then the record is normalized.
    """
    source_file = str(record.get("source_file", ""))
    upgraded = dict(record)
    if source_file and not upgraded.get("source_origin"):
        origin = portable_origin(source_file)
        if origin != "unknown":
            upgraded["source_origin"] = origin
    if source_file:
        upgraded["source_file"] = portable_path(source_file)
    metadata = upgraded.get("metadata")
    if isinstance(metadata, dict):
        upgraded["metadata"] = portable_metadata(metadata)
    return upgraded
