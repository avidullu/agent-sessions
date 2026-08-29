"""Tests for machine-readable local export routine discovery."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from agent_sessions.cli import main
from agent_sessions.routine import SCHEMA, discover_routine


def _fake_crontab(tmp_path: Path, content: str = "") -> tuple[Path, dict[str, str]]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state = tmp_path / "crontab.txt"
    if content:
        state.write_text(content, encoding="utf-8")
    crontab = fake_bin / "crontab"
    crontab.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  -l) [[ -f "$FAKE_CRONTAB_STATE" ]] && cat "$FAKE_CRONTAB_STATE" || exit 1 ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    crontab.chmod(crontab.stat().st_mode | stat.S_IXUSR)
    env = {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_CRONTAB_STATE": str(state),
        "XDG_DATA_HOME": str(tmp_path / "data"),
    }
    return state, env


@pytest.mark.skipif(os.name == "nt", reason="POSIX routine contract")
def test_discover_routine_is_installable_without_cron_entry(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "local-export.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "scripts" / "install-local-export-schedule.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    _, env = _fake_crontab(tmp_path)

    report = discover_routine(repo, system="linux", env=env)

    assert report["schema"] == SCHEMA
    assert report["machine"] == {
        "os": "linux",
        "scheduler": "cron",
        "scheduler_available": True,
    }
    assert report["automation"]["state"] == "installable"
    assert report["automation"]["installed"] is False
    assert report["automation"]["updatable"] is True
    assert report["automation"]["actions"]["install_or_update"][0] == "bash"
    assert "hostname" not in json.dumps(report).casefold()


@pytest.mark.skipif(os.name == "nt", reason="POSIX routine contract")
def test_discover_routine_distinguishes_current_and_update_available(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    export = scripts / "local-export.sh"
    export.write_text("#!/bin/sh\n", encoding="utf-8")
    installer = scripts / "install-local-export-schedule.sh"
    installer.write_text("#!/bin/sh\n", encoding="utf-8")
    log_dir = (tmp_path / "data" / "agent-sessions" / "logs").resolve()
    marker = "# agent-sessions local-export (managed by install-local-export-schedule.sh)"
    current = (
        f"{marker}\n"
        f"30 7 * * * AGENT_SESSIONS_ROUTINE_SCHEMA=1 '{export.resolve()}' "
        f"--log-dir '{log_dir}' --write-primary-marker\n"
    )
    state, env = _fake_crontab(tmp_path, current)

    report = discover_routine(repo, system="linux", env=env)
    assert report["automation"]["state"] == "current"

    state.write_text(current.replace("30 7", "0 9"), encoding="utf-8")
    report = discover_routine(repo, system="linux", env=env)
    assert report["automation"]["state"] == "update_available"
    assert report["automation"]["reasons"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX routine contract")
def test_routine_status_cli_writes_versioned_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "local-export.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "scripts" / "install-local-export-schedule.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    _, env = _fake_crontab(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    result = main(["--repo-root", str(repo), "routine", "status", "--json"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == SCHEMA
    assert payload["automation"]["routine_id"] == "agent-sessions.local-export"
