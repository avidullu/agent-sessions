"""One-time migration: rewrite tracked catalogs to the portable-path convention.

Applies the same transforms the writers now apply (``agent_sessions.portable_paths``)
to the data files that were committed before the convention existed:

- ``archive/index.jsonl``          — source_file, metadata, backfilled source_origin
- ``baseline/handoffs/index.jsonl`` — source_file, trace
- ``baseline/proposals/*.json``     — trace/source_file fields (recursive)
- text files with encoded/absolute home paths (project pages, DISCOVERY)

Idempotent: re-running on migrated files is a no-op. Run from the repo root:

    python -m tools.migrate_portable_paths
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_sessions.portable_paths import portable_metadata, portable_path, portable_record

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_FILES = (
    "docs/DISCOVERY.md",
    "baseline/projects/badminton-highlight-indexer/README.md",
    "baseline/projects/khelsutra/README.md",
    "baseline/projects/muneem/README.md",
)


def migrate_jsonl(path: Path, transform: Callable[[dict[str, Any]], dict[str, Any]]) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    changed = False
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        migrated = transform(record)
        dumped = json.dumps(migrated, ensure_ascii=False)
        if dumped != line:
            changed = True
        out.append(dumped)
    if changed:
        path.write_text("".join(f"{line}\n" for line in out), encoding="utf-8", newline="\n")
    return changed


def migrate_json(path: Path) -> bool:
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    migrated = portable_metadata(data)
    dumped = json.dumps(migrated, ensure_ascii=False, indent=2) + "\n"
    if dumped != original:
        path.write_text(dumped, encoding="utf-8", newline="\n")
        return True
    return False


# Text files embed paths mid-line ("- Root: `C:\\Users\\...`"), so the
# home-prefix patterns are applied unanchored here — unlike the library
# transform, which only rewrites values that are paths in their own right.
_UNANCHORED_HOME_RES = (
    re.compile(r"[\\/]{2}wsl(?:\.localhost|\$)?[\\/][^\\/`\s]+[\\/]home[\\/][^\\/`\s]+"),
    re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/`\s]+"),
    re.compile(r"/mnt/[A-Za-z]/Users/[^/`\s]+"),
    re.compile(r"(?<![\w.])/home/[^/`\s]+"),
    re.compile(r"(?<![\w.])/Users/[^/`\s]+"),
)


def migrate_text(path: Path) -> bool:
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    migrated = original
    for pattern in _UNANCHORED_HOME_RES:
        migrated = pattern.sub("~", migrated)
    migrated = "\n".join(portable_path(line) for line in migrated.split("\n"))
    if migrated != original:
        path.write_text(migrated, encoding="utf-8", newline="\n")
        return True
    return False


def main() -> int:
    changed: list[str] = []

    index_path = REPO_ROOT / "archive" / "index.jsonl"
    if migrate_jsonl(index_path, portable_record):
        changed.append(str(index_path.relative_to(REPO_ROOT)))

    handoffs_path = REPO_ROOT / "baseline" / "handoffs" / "index.jsonl"
    if migrate_jsonl(handoffs_path, portable_metadata):
        changed.append(str(handoffs_path.relative_to(REPO_ROOT)))

    for proposal in sorted((REPO_ROOT / "baseline" / "proposals").glob("*.json")):
        if migrate_json(proposal):
            changed.append(str(proposal.relative_to(REPO_ROOT)))

    for name in TEXT_FILES:
        if migrate_text(REPO_ROOT / name):
            changed.append(name)

    if changed:
        print("migrated:")
        for name in changed:
            print(f"  {name}")
    else:
        print("nothing to migrate (already portable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
