"""Release metadata must identify the artifact a tag will publish."""

from __future__ import annotations

import tomllib
from pathlib import Path

from agent_sessions import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_and_project_versions_match() -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project_version = tomllib.load(handle)["project"]["version"]
    assert __version__ == project_version


def test_release_workflow_names_distribution_and_checks_tag() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "project\n# `agent-session-hub`" in workflow
    assert "Verify tag matches package version" in workflow
    assert 'tag = os.environ["GITHUB_REF_NAME"]' in workflow
    assert 'expected = f"v{version}"' in workflow
