"""Machine-specific path template expansion."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathTemplateContext:
    values: Mapping[str, str]

    @classmethod
    def from_environment(cls, repo_root: Path) -> PathTemplateContext:
        home = Path.home()
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        wsl_distro = os.environ.get("AGENT_ARCHIVE_WSL_DISTRO") or discover_wsl_distro()
        wsl_user = os.environ.get("AGENT_ARCHIVE_WSL_USER") or discover_wsl_user(wsl_distro)
        wsl_home = make_wsl_home(wsl_distro, wsl_user)
        values = {
            "repo_root": str(repo_root),
            "home": str(home),
            "userprofile": str(home),
            "appdata": appdata,
            "localappdata": localappdata,
            "wsl_distro": wsl_distro,
            "wsl_user": wsl_user,
            "wsl_home": wsl_home,
            "wsl_vscode_server": f"{wsl_home}\\.vscode-server" if wsl_home else "",
        }
        return cls(values)

    def resolve(self, template: str) -> Path:
        for key in ("wsl_home", "wsl_vscode_server"):
            if template.startswith("{" + key + "}") and not self.values.get(key):
                remainder = template.split("}", 1)[1].lstrip("/\\")
                return Path(f"__missing_{key}__") / remainder
        try:
            rendered = template.format_map(_StrictTemplateValues(self.values))
        except KeyError as exc:
            raise SystemExit(f"Unknown path template variable {{{exc.args[0]}}} in {template!r}") from exc
        return Path(os.path.expandvars(rendered)).expanduser()


class _StrictTemplateValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        raise KeyError(key)


def discover_wsl_distro() -> str:
    output = run_command(["wsl.exe", "-l", "-q"])
    for line in clean_wsl_output(output).splitlines():
        name = line.strip()
        if name:
            return name
    return ""


def discover_wsl_user(distro: str) -> str:
    if not distro:
        return ""
    output = run_command(["wsl.exe", "-d", distro, "--exec", "sh", "-lc", 'printf "%s" "$USER"'])
    user = clean_wsl_output(output).strip()
    return user or os.environ.get("USERNAME", "")


def make_wsl_home(distro: str, user: str) -> str:
    if not distro or not user:
        return ""
    return f"\\\\wsl.localhost\\{distro}\\home\\{user}"


def run_command(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def clean_wsl_output(value: str) -> str:
    return value.replace("\x00", "").replace("\r", "")
