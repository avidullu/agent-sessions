"""Explicit, local-only first-run setup for an installed wheel."""

from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path


def initialize_archive(root: Path, archive_dir: Path | None = None) -> Path:
    """Create a private-by-default workspace without exporting or overwriting config."""
    root = root.expanduser().resolve()
    target = root / "sources.toml"
    if target.exists():
        raise SystemExit(f"Configuration already exists: {target}. Kept unchanged; edit it to change paths.")
    archive = archive_dir.expanduser() if archive_dir else root / "archive"
    if not archive.is_absolute():
        archive = root / archive
    archive = archive.resolve()
    if archive == root or archive == root / "raw":
        raise SystemExit("Choose an archive subdirectory, separate from the workspace root and raw directory.")
    if archive.parent != root:
        raise SystemExit("Router output must be a direct child of the workspace. Set --repo-root to its parent.")
    if (root / ".gitignore").is_symlink():
        raise SystemExit("Workspace .gitignore is a symlink; choose a workspace with a local ignore policy.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for directory in (archive, root / "raw"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Do not replace an existing ignore policy, including a symlink.
        try:
            with (directory / ".gitignore").open("x", encoding="utf-8") as stream:
                stream.write("# Local session data; never stage this directory by default.\n*\n")
        except FileExistsError:
            pass
    with (root / ".gitignore").open("a", encoding="utf-8") as stream:
        stream.write("\n# Agent Sessions local configuration\n/sources.toml\n")
    template = files("agent_sessions").joinpath("default_sources.toml").read_text(encoding="utf-8")
    template = template.replace('archive_dir = "archive"',
                                f"archive_dir = {json.dumps(archive.as_posix(), ensure_ascii=False)}")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(template)
    return archive
