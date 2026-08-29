"""Release metadata must identify the artifact a tag will publish."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from agent_sessions import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tag_check_script() -> str:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    marker = "python - <<'PY'\n"
    start = workflow.index(marker) + len(marker)
    end = workflow.index("          PY\n", start)
    body = workflow[start:end]
    return "\n".join(line[10:] if line.startswith("          ") else line for line in body.splitlines())


def test_package_and_project_versions_match() -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project_version = tomllib.load(handle)["project"]["version"]
    assert __version__ == project_version == "0.3.0.dev0"


def test_release_workflow_names_distribution_and_checks_tag() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "project\n# `agent-session-hub`" in workflow
    assert "Verify tag matches package version" in workflow
    assert "Trusted Publishing" in workflow
    assert "from packaging.version import Version" in workflow
    assert "parsed.is_devrelease or parsed.is_prerelease" in workflow


def test_dev_tag_is_rejected_even_when_it_matches_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.3.0.dev0"\n', encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", _tag_check_script()],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_REF_NAME": "v0.3.0.dev0"},
    )
    assert completed.returncode != 0
    assert "non-final" in (completed.stderr + completed.stdout)


def test_final_matching_tag_is_accepted(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.3.0"\n', encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", _tag_check_script()],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_REF_NAME": "v0.3.0"},
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""


def test_mismatched_final_tag_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.3.0"\n', encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", _tag_check_script()],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_REF_NAME": "v0.2.0"},
    )
    assert completed.returncode != 0
    assert "does not match" in (completed.stderr + completed.stdout)
