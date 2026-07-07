"""Import-hygiene regression tests for the baseline module split (TD10).

Each module must be importable on its own in a cold interpreter. This fails if
anyone reintroduces a module-level import cycle (the old
``baseline`` ↔ ``baseline_calibration`` cycle was hidden by a function-level
import; importing each module first proves the graph stays acyclic).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

BASELINE_MODULES = (
    "agent_sessions.baseline_types",
    "agent_sessions.baseline_settings",
    "agent_sessions.baseline_predictions",
    "agent_sessions.baseline_report",
    "agent_sessions.baseline_promote",
    "agent_sessions.baseline_calibration",
    "agent_sessions.baseline",
    "agent_sessions.baseline_eval",
    "agent_sessions.baseline_lint",
    "agent_sessions.baseline_publish",
    "agent_sessions.baseline_ingest",
    "agent_sessions.baseline_agent",
    "agent_sessions.baseline_handoffs",
    "agent_sessions.baseline_replay",
    "agent_sessions.baseline_redaction",
    "agent_sessions.cli",
)


@pytest.mark.parametrize("module", BASELINE_MODULES)
def test_module_imports_standalone(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"import {module} failed:\n{result.stderr}"
