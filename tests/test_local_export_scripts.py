"""Tests for local-only export automation scripts."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from tests.bash_support import BASH, requires_bash

REPO_ROOT = Path(__file__).resolve().parents[1]


@requires_bash
def test_local_export_sh_help() -> None:
    script = REPO_ROOT / "scripts" / "local-export.sh"
    assert script.is_file()
    if os.name != "nt":
        assert script.stat().st_mode & stat.S_IXUSR
    assert BASH is not None
    completed = subprocess.run(
        [BASH, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0
    assert "without any git operations" in completed.stdout
    assert "--log-dir" in completed.stdout
    assert "--break-lock" in completed.stdout


@pytest.mark.parametrize("option", ["--python", "--source", "--log-dir"])
@requires_bash
def test_local_export_sh_rejects_missing_option_value(option: str) -> None:
    assert BASH is not None
    completed = subprocess.run(
        [BASH, str(REPO_ROOT / "scripts" / "local-export.sh"), option],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 2
    assert f"{option} requires a value" in completed.stderr


@requires_bash
def test_install_local_export_schedule_sh_help() -> None:
    script = REPO_ROOT / "scripts" / "install-local-export-schedule.sh"
    assert script.is_file()
    if os.name != "nt":
        assert script.stat().st_mode & stat.S_IXUSR
    assert BASH is not None
    completed = subprocess.run(
        [BASH, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0
    assert "crontab" in completed.stdout
    assert "--uninstall" in completed.stdout


@pytest.mark.skipif(os.name == "nt", reason="POSIX crontab behavior")
def test_install_schedule_quotes_cron_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo with space%and'apostrophe"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    for name in ("local-export.sh", "install-local-export-schedule.sh"):
        target = scripts / name
        shutil.copy2(REPO_ROOT / "scripts" / name, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    crontab_state = tmp_path / "crontab.txt"
    fake_crontab = fake_bin / "crontab"
    fake_crontab.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  -l) [[ -f "$FAKE_CRONTAB_STATE" ]] && cat "$FAKE_CRONTAB_STATE" || exit 1 ;;
  -r) rm -f "$FAKE_CRONTAB_STATE" ;;
  -) cat >"$FAKE_CRONTAB_STATE" ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    fake_crontab.chmod(fake_crontab.stat().st_mode | stat.S_IXUSR)

    log_dir = tmp_path / "logs with space%and'apostrophe"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_CRONTAB_STATE"] = str(crontab_state)
    completed = subprocess.run(
        [
            "bash",
            str(scripts / "install-local-export-schedule.sh"),
            "--log-dir",
            str(log_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    cron_line = crontab_state.read_text(encoding="utf-8").splitlines()[-1]

    def cron_quote(value: Path) -> str:
        return "'" + str(value).replace("'", "'\\''").replace("%", "\\%") + "'"

    assert cron_quote(scripts / "local-export.sh") in cron_line
    assert "AGENT_SESSIONS_ROUTINE_SCHEMA=1" in cron_line
    assert f"--log-dir {cron_quote(log_dir)}" in cron_line
    command = cron_line.split(maxsplit=5)[5].replace("\\%", "%")
    syntax = subprocess.run(["sh", "-n", "-c", command], check=False)
    assert syntax.returncode == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX git behavior")
def test_public_clone_ignores_untracked_local_catalog(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(REPO_ROOT / ".gitignore", repo / ".gitignore")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    for relative in ("archive/.router-index.jsonl", "archive/index.jsonl", "archive/INDEX.md"):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("private local catalog\n", encoding="utf-8")
        ignored = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-q", relative],
            check=False,
        )
        assert ignored.returncode == 0, relative


def test_local_export_ps1_present() -> None:
    assert (REPO_ROOT / "scripts" / "local-export.ps1").is_file()
    assert (REPO_ROOT / "scripts" / "install-local-export-schedule.ps1").is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX lock behavior")
def test_local_export_lock_is_not_evicted_by_age(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "local-export.sh"
    shutil.copy2(REPO_ROOT / "scripts" / "local-export.sh", script)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    lock_dir = repo / ".local-export.lock"
    lock_dir.mkdir()
    (lock_dir / "token").write_text("active-owner\n", encoding="utf-8")
    os.utime(lock_dir, (1, 1))

    blocked = subprocess.run(
        ["bash", str(script), "--python", "/bin/true", "--no-status"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert blocked.returncode == 1
    assert "another export may be running" in blocked.stderr
    assert (lock_dir / "token").read_text(encoding="utf-8") == "active-owner\n"

    recovered = subprocess.run(
        [
            "bash",
            str(script),
            "--python",
            "/bin/true",
            "--no-status",
            "--break-lock",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert not lock_dir.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell behavior")
def test_local_export_ps1_propagates_native_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    tools = repo / "tools"
    scripts.mkdir(parents=True)
    tools.mkdir()
    script = scripts / "local-export.ps1"
    shutil.copy2(REPO_ROOT / "scripts" / "local-export.ps1", script)
    (tools / "agent_archive.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    powershell = shutil.which("powershell.exe")
    assert powershell is not None

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Python",
            sys.executable,
            "-NoStatus",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "export failed with exit code 7" in completed.stderr
    assert "local-export: done" not in completed.stdout
    assert not (repo / ".local-export.lock").exists()


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
    assert any(
        source.get("name") == "zai-vscode-wsl-ubuntu-inventory"
        for source in data["sources"]
    )


def test_automation_doc_describes_two_modes() -> None:
    text = (REPO_ROOT / "docs" / "AUTOMATION.md").read_text(encoding="utf-8")
    assert "Local-only primary host" in text
    assert "Private catalog sync" in text
    assert "install-local-export-schedule" in text
