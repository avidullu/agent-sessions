"""Tests for the tools/agent_archive.py command wrapper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_agent_archive_wrapper_imports_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "agent_archive.py"), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Export local coding-agent sessions" in result.stdout
