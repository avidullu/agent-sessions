"""Smoke tests for local-export automation scripts."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_local_export_sh_help() -> None:
    script = REPO_ROOT / "scripts" / "local-export.sh"
    assert script.is_file()
    assert script.stat().st_mode & stat.S_IXUSR
    completed = subprocess.run(
        ["bash", str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0
    assert "without any git operations" in completed.stdout
    assert "--log-dir" in completed.stdout


def test_install_local_export_schedule_sh_help() -> None:
    script = REPO_ROOT / "scripts" / "install-local-export-schedule.sh"
    assert script.is_file()
    assert script.stat().st_mode & stat.S_IXUSR
    completed = subprocess.run(
        ["bash", str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0
    assert "crontab" in completed.stdout
    assert "--uninstall" in completed.stdout


def test_local_export_ps1_present() -> None:
    assert (REPO_ROOT / "scripts" / "local-export.ps1").is_file()
    assert (REPO_ROOT / "scripts" / "install-local-export-schedule.ps1").is_file()


def test_sources_example_has_wsl_windows_mount_section() -> None:
    import tomllib

    text = (REPO_ROOT / "sources.example.toml").read_text(encoding="utf-8")
    assert "WSL reading Windows-native" in text
    assert "/mnt/c/Users/<you>/.claude/projects" in text
    data = tomllib.loads(text)
    # No orphaned top-level glob from the pre-fix example file.
    assert "glob" not in data
    assert isinstance(data.get("sources"), list)
    assert data["sources"]


def test_automation_doc_describes_two_modes() -> None:
    text = (REPO_ROOT / "docs" / "AUTOMATION.md").read_text(encoding="utf-8")
    assert "Local-only primary host" in text
    assert "Private catalog sync" in text
    assert "install-local-export-schedule" in text
