"""Locating a usable ``bash`` for subprocess tests, including native Windows.

On native Windows ``shutil.which("bash")`` usually finds
``C:\\Windows\\System32\\bash.exe`` — the **WSL launcher**, not a POSIX shell.
It cannot consume the native Windows paths these subprocess tests pass, so a
test that uses it fails with a confusing "No such file or directory" rather
than a real assertion failure. Git for Windows ships a real POSIX bash next to
``git.exe``, which is what we want.

This lived in ``test_pre_push_hook.py``. It is shared because a second test
module copied ``shutil.which("bash")`` verbatim and broke the Windows legs —
one definition of a platform quirk, not two.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

GIT = shutil.which("git")


def find_bash() -> str | None:
    """Prefer Git Bash over the unrelated WSL launcher on native Windows."""
    if os.name == "nt" and GIT is not None:
        git_path = Path(GIT).resolve()
        # Git for Windows normally resolves to Git/cmd/git.exe. Its POSIX
        # shell is Git/bin/bash.exe; System32/bash.exe is the WSL launcher and
        # cannot consume the native paths used by these subprocess tests.
        git_bash = git_path.parent.parent / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    return shutil.which("bash")


BASH = find_bash()

requires_bash = pytest.mark.skipif(BASH is None, reason="bash is not available on this platform")
requires_git = pytest.mark.skipif(BASH is None or GIT is None, reason="bash and git are required")
