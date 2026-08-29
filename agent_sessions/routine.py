"""Discover the local-only export routine without changing machine state."""

from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA = "agent-sessions.routine-discovery.v1"
ROUTINE_SCHEMA = "1"
CRON_MARKER = "# agent-sessions local-export (managed by install-local-export-schedule.sh)"
WINDOWS_TASK_NAME = "Agent Sessions Local Export"
WINDOWS_TASK_DESCRIPTION = f"Agent Sessions managed local-export routine schema v{ROUTINE_SCHEMA}"


def _default_log_dir(system: str, env: Mapping[str, str]) -> Path:
    configured = env.get("AGENT_SESSIONS_LOG_DIR")
    if configured:
        return Path(configured).expanduser()
    if system == "windows":
        base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "agent-sessions" / "logs"
    data_home = env.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "agent-sessions" / "logs"


def _action_commands(
    repo_root: Path,
    *,
    system: str,
    hour: int,
    minute: int,
    log_dir: Path,
    pdf: bool,
) -> dict[str, list[str]]:
    if system == "windows":
        installer = repo_root / "scripts" / "install-local-export-schedule.ps1"
        base = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(installer),
            "-Hour",
            str(hour),
            "-Minute",
            str(minute),
            "-LogDir",
            str(log_dir),
        ]
        if pdf:
            base.append("-Pdf")
        return {"install_or_update": base, "uninstall": [*base[:6], "-Uninstall"]}

    installer = repo_root / "scripts" / "install-local-export-schedule.sh"
    base = [
        "bash",
        str(installer),
        "--hour",
        str(hour),
        "--minute",
        str(minute),
        "--log-dir",
        str(log_dir),
    ]
    if pdf:
        base.append("--pdf")
    return {"install_or_update": base, "uninstall": ["bash", str(installer), "--uninstall"]}


def _cron_state(
    repo_root: Path,
    *,
    hour: int,
    minute: int,
    log_dir: Path,
    pdf: bool,
    env: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    crontab = shutil.which("crontab", path=env.get("PATH"))
    if crontab is None:
        return {
            "scheduler": "cron",
            "scheduler_available": False,
            "installed": False,
            "managed": False,
            "state": "unsupported",
        }, ["crontab executable is unavailable"]

    completed = subprocess.run(
        [crontab, "-l"],
        check=False,
        capture_output=True,
        text=True,
        env=dict(env),
    )
    lines = completed.stdout.splitlines() if completed.returncode == 0 else []
    marker_indexes = [index for index, line in enumerate(lines) if line == CRON_MARKER]
    cron_lines = [lines[index + 1] for index in marker_indexes if index + 1 < len(lines)]
    reasons: list[str] = []

    if not marker_indexes:
        return {
            "scheduler": "cron",
            "scheduler_available": True,
            "installed": False,
            "managed": False,
            "state": "installable",
        }, reasons

    state = "current"
    if len(marker_indexes) != 1 or len(cron_lines) != 1:
        state = "repair_required"
        reasons.append("managed cron block is duplicated or incomplete")

    installed_schedule: dict[str, Any] = {}
    export_script = str((repo_root / "scripts" / "local-export.sh").resolve())
    if cron_lines:
        fields = cron_lines[0].split(maxsplit=5)
        if len(fields) != 6:
            state = "repair_required"
            reasons.append("managed cron line is malformed")
        else:
            installed_schedule = {"minute": fields[0], "hour": fields[1]}
            try:
                command = shlex.split(fields[5])
            except ValueError:
                command = []
                state = "repair_required"
                reasons.append("managed cron command is not valid shell syntax")
            expected = {
                "schema": f"AGENT_SESSIONS_ROUTINE_SCHEMA={ROUTINE_SCHEMA}",
                "script": export_script,
                "hour": str(hour),
                "minute": str(minute),
                "log_dir": str(log_dir),
                "pdf": pdf,
            }
            actual_log_dir = ""
            if "--log-dir" in command:
                position = command.index("--log-dir")
                if position + 1 < len(command):
                    actual_log_dir = command[position + 1]
            current = (
                fields[:5] == [str(minute), str(hour), "*", "*", "*"]
                and expected["schema"] in command
                and expected["script"] in command
                and actual_log_dir == expected["log_dir"]
                and ("--pdf" in command) == expected["pdf"]
                and Path(export_script).is_file()
            )
            if state == "current" and not current:
                state = "update_available"
                reasons.append("managed cron entry differs from the requested routine specification")

    return {
        "scheduler": "cron",
        "scheduler_available": True,
        "installed": True,
        "managed": True,
        "state": state,
        "installed_schedule": installed_schedule,
    }, reasons


def _windows_state(
    repo_root: Path,
    *,
    hour: int,
    minute: int,
    log_dir: Path,
    pdf: bool,
    env: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    powershell = shutil.which("powershell.exe", path=env.get("PATH")) or shutil.which("pwsh", path=env.get("PATH"))
    if powershell is None:
        return {
            "scheduler": "windows-task-scheduler",
            "scheduler_available": False,
            "installed": False,
            "managed": False,
            "state": "unsupported",
        }, ["PowerShell is unavailable"]

    query = (
        f"$t=Get-ScheduledTask -TaskName '{WINDOWS_TASK_NAME}' -ErrorAction SilentlyContinue;"
        "if($null -eq $t){'null'}else{"
        "[pscustomobject]@{description=$t.Description;execute=$t.Actions.Execute;"
        "arguments=$t.Actions.Arguments;start=$t.Triggers.StartBoundary}|ConvertTo-Json -Compress}"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-Command", query],
        check=False,
        capture_output=True,
        text=True,
        env=dict(env),
    )
    if completed.returncode != 0:
        return {
            "scheduler": "windows-task-scheduler",
            "scheduler_available": True,
            "installed": False,
            "managed": False,
            "state": "unsupported",
        }, ["Windows Task Scheduler query failed"]
    raw = completed.stdout.strip()
    if not raw or raw == "null":
        return {
            "scheduler": "windows-task-scheduler",
            "scheduler_available": True,
            "installed": False,
            "managed": False,
            "state": "installable",
        }, []

    try:
        task = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "scheduler": "windows-task-scheduler",
            "scheduler_available": True,
            "installed": True,
            "managed": False,
            "state": "repair_required",
        }, ["Windows Task Scheduler returned an unreadable task"]

    arguments = str(task.get("arguments", ""))
    expected_script = str((repo_root / "scripts" / "local-export.ps1").resolve())
    expected_time = f"T{hour:02d}:{minute:02d}:"
    current = (
        str(task.get("description", "")) == WINDOWS_TASK_DESCRIPTION
        and expected_script.casefold() in arguments.casefold()
        and str(log_dir).casefold() in arguments.casefold()
        and ("-Pdf" in arguments) == pdf
        and expected_time in str(task.get("start", ""))
        and Path(expected_script).is_file()
    )
    state = "current" if current else "update_available"
    reasons = [] if current else ["managed scheduled task differs from the requested routine specification"]
    return {
        "scheduler": "windows-task-scheduler",
        "scheduler_available": True,
        "installed": True,
        "managed": str(task.get("description", "")).startswith("Agent Sessions managed"),
        "state": state,
        "installed_schedule": {"start": task.get("start", "")},
    }, reasons


def discover_routine(
    repo_root: Path,
    *,
    hour: int = 7,
    minute: int = 30,
    log_dir: Path | None = None,
    pdf: bool = False,
    system: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return a versioned install/update status for the local export routine."""

    resolved_repo = repo_root.resolve()
    effective_env = dict(os.environ if env is None else env)
    detected_system = (system or platform.system()).casefold()
    normalized_system = "windows" if detected_system.startswith("win") else detected_system
    desired_log_dir = (log_dir or _default_log_dir(normalized_system, effective_env)).expanduser().resolve()
    actions = _action_commands(
        resolved_repo,
        system=normalized_system,
        hour=hour,
        minute=minute,
        log_dir=desired_log_dir,
        pdf=pdf,
    )

    if normalized_system == "windows":
        automation, reasons = _windows_state(
            resolved_repo,
            hour=hour,
            minute=minute,
            log_dir=desired_log_dir,
            pdf=pdf,
            env=effective_env,
        )
    elif normalized_system in {"linux", "darwin"}:
        automation, reasons = _cron_state(
            resolved_repo,
            hour=hour,
            minute=minute,
            log_dir=desired_log_dir,
            pdf=pdf,
            env=effective_env,
        )
    else:
        automation = {
            "scheduler": "none",
            "scheduler_available": False,
            "installed": False,
            "managed": False,
            "state": "unsupported",
        }
        reasons = [f"unsupported operating system: {normalized_system}"]

    automation.update(
        {
            "routine_id": "agent-sessions.local-export",
            "routine_schema": ROUTINE_SCHEMA,
            "supported": automation["scheduler_available"],
            "updatable": automation["scheduler_available"],
            "desired_schedule": {
                "kind": "daily",
                "hour": hour,
                "minute": minute,
                "pdf": pdf,
            },
            "actions": actions,
            "reasons": reasons,
        }
    )
    return {
        "schema": SCHEMA,
        "machine": {
            "os": normalized_system,
            "scheduler": automation["scheduler"],
            "scheduler_available": automation["scheduler_available"],
        },
        "automation": automation,
        "negative_space": [
            "discovery does not run the export or inspect private transcripts",
            "installation does not push catalogs or grant remote access",
            "routine health is not an assurance verdict",
        ],
    }


def format_routine_status(report: Mapping[str, Any]) -> str:
    automation = report["automation"]
    desired = automation["desired_schedule"]
    lines = [
        f"Agent Sessions local-export routine: {automation['state']}",
        f"  machine: {report['machine']['os']} / {automation['scheduler']}",
        f"  desired: daily {desired['hour']:02d}:{desired['minute']:02d}",
        f"  installed: {'yes' if automation['installed'] else 'no'}",
        f"  updatable: {'yes' if automation['updatable'] else 'no'}",
    ]
    for reason in automation["reasons"]:
        lines.append(f"  reason: {reason}")
    action: Sequence[str] = automation["actions"]["install_or_update"]
    if automation["state"] != "current" and automation["supported"]:
        lines.append(f"  next: {shlex.join(action)}")
    return "\n".join(lines)
