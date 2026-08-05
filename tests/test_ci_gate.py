"""The honest-gate invariant.

Forgejo maps a SKIPPED job to ``success`` in the commit-status API, so a job
carrying ``if:`` renders a green check on a pull request even though it never
executed. That is not hypothetical here: ``test-windows`` carried
``if: github.server_url == 'https://github.com'`` while GitHub Actions was
disabled on the backup mirror, so the native-Windows legs ran on no forge at
all and still reported ``CI / test (py 3.11, windows-latest) - success``.

``scripts/ci-gate.sh`` is the one check that can tell "passed" from "never
ran", because it asserts on ``needs.<job>.result``. These tests pin both the
script's behaviour and the workflow wiring that makes it meaningful.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.bash_support import BASH, requires_bash

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "ci-gate.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(
        [BASH, str(GATE), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@requires_bash
def test_all_success_passes() -> None:
    result = run_gate("test=success", "lint=success")
    assert result.returncode == 0, result.stderr
    assert "PASSED" in result.stdout


@requires_bash
def test_skipped_job_fails_the_gate() -> None:
    """The regression this whole mechanism exists for.

    A skipped job is reported as ``success`` by Forgejo's status API. The gate
    must reject it, or the merge gate is decorative.
    """
    result = run_gate("test=success", "test-windows=skipped")
    assert result.returncode == 1
    assert "SKIPPED" in result.stderr
    assert "not a passing job" in result.stderr


@requires_bash
@pytest.mark.parametrize("bad", ["failure", "cancelled"])
def test_non_success_results_fail(bad: str) -> None:
    result = run_gate(f"test={bad}")
    assert result.returncode == 1
    assert "did not succeed" in result.stderr


@requires_bash
def test_empty_result_fails() -> None:
    """An empty result means the job is absent from ``needs:``.

    The expression expands to nothing, which must not read as an absent check.
    """
    result = run_gate("test=success", "test-windows=")
    assert result.returncode == 1
    assert "empty result" in result.stderr


@requires_bash
def test_no_arguments_fails_closed() -> None:
    """A gate given nothing to check must never report a pass."""
    result = run_gate()
    assert result.returncode == 1
    assert "refusing to pass" in result.stderr


@requires_bash
def test_allow_skipped_permits_but_reports_not_run() -> None:
    result = run_gate("--allow-skipped", "test-windows", "test=success", "test-windows=skipped")
    assert result.returncode == 0
    assert "NOT RUN" in result.stdout
    # It must not claim coverage it does not have.
    assert "every required job ran" not in result.stdout
    assert "coverage is incomplete" in result.stdout


@requires_bash
def test_allow_skipped_requires_a_value() -> None:
    result = run_gate("--allow-skipped")
    assert result.returncode == 2


def workflow_jobs() -> list[str]:
    """Top-level job keys in ci.yml, in file order."""
    body = WORKFLOW.read_text(encoding="utf-8")
    jobs_section = body[body.index("\njobs:") :]
    return re.findall(r"^  ([A-Za-z0-9_-]+):[ \t]*$", jobs_section, flags=re.MULTILINE)


def workflow_job_block(body: str, job: str) -> str:
    """Return one top-level job block without matching sibling jobs."""
    start = re.search(rf"^  {re.escape(job)}:[ \t]*$", body, flags=re.MULTILINE)
    assert start is not None, f"workflow has no {job!r} job"
    sibling = re.search(r"^  [A-Za-z0-9_-]+:[ \t]*$", body[start.end() :], flags=re.MULTILINE)
    end = start.end() + sibling.start() if sibling is not None else len(body)
    return body[start.start() : end]


def test_workflow_has_a_ci_gate_job() -> None:
    assert "ci-gate" in workflow_jobs()


def test_ci_gate_runs_always() -> None:
    """Without always(), a failed dependency skips the gate - which reports success."""
    body = WORKFLOW.read_text(encoding="utf-8")
    gate = workflow_job_block(body, "ci-gate")
    assert re.search(r"^\s*if:\s*\$\{\{\s*always\(\)\s*\}\}\s*$", gate, flags=re.MULTILINE)
    assert len(re.findall(r"^\s*if:\s*\$\{\{\s*always\(\)\s*\}\}\s*$", body, flags=re.MULTILINE)) == 1


def test_every_job_is_covered_by_the_gate() -> None:
    """A job outside the gate can fail or be skipped without failing CI."""
    body = WORKFLOW.read_text(encoding="utf-8")
    gate = workflow_job_block(body, "ci-gate")
    needs = re.search(r"^\s*needs:\s*\[(?P<jobs>[^\]]*)\]", gate, flags=re.MULTILINE)
    assert needs is not None, "ci-gate has no needs: list"
    gated = {name.strip() for name in needs.group("jobs").split(",") if name.strip()}

    for job in workflow_jobs():
        if job == "ci-gate":
            continue
        assert job in gated, f"job {job!r} is not in ci-gate's needs: list"
        # Being in needs: is not enough - the result must reach the assertion.
        assert f'"{job}=${{{{ needs.{job}.result }}}}"' in gate, (
            f"job {job!r} is in needs: but its result is never passed to ci-gate.sh"
        )


def test_gate_inspection_ignores_decoy_needs_on_another_job() -> None:
    """A sibling's needs:/always() stanza must never satisfy gate checks."""
    body = WORKFLOW.read_text(encoding="utf-8")
    mutated = body.replace("  test:\n", "  test:\n    needs: [decoy]\n    if: ${{ always() }}\n", 1)
    gate = workflow_job_block(mutated, "ci-gate")
    assert "needs: [decoy]" not in gate
    assert gate.count("if: ${{ always() }}") == 1


def test_no_job_is_silently_forge_conditional() -> None:
    """Only ci-gate's always() may use a job-level ``if:``.

    Any other ``if:`` reintroduces a job that can be skipped-to-green.
    """
    body = WORKFLOW.read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in body.splitlines()
        if re.match(r"^\s*if:", line) and not re.search(r"\$\{\{\s*always\(\)\s*\}\}", line)
    ]
    assert not offenders, f"unexpected job-level if: in ci.yml: {offenders}"


def test_gate_runner_label_is_unconditional() -> None:
    """A gate that cannot be scheduled on some forge is itself a false green."""
    body = WORKFLOW.read_text(encoding="utf-8")
    gate_block = workflow_job_block(body, "ci-gate")
    runs_on = re.search(r"^\s*runs-on:\s*(?P<label>.+)$", gate_block, flags=re.MULTILINE)
    assert runs_on is not None
    assert "${{" not in runs_on.group("label"), (
        "ci-gate must use a literal runner label, not a conditional expression"
    )


def test_windows_job_bootstraps_without_reusable_actions() -> None:
    """The older Windows runner cannot clone action repositories."""
    body = WORKFLOW.read_text(encoding="utf-8")
    windows = workflow_job_block(body, "test-windows")
    assert "uses:" not in windows
    assert "shell: pwsh" not in windows
    assert windows.count("shell: powershell") == 4
    assert body.count("\n        env:\n") == 1
    assert "CI_REPOSITORY_TOKEN: ${{ github.token }}" in windows
    assert "fetch --no-tags --depth=1 origin $env:GITHUB_SHA" in windows
    assert 'ci-python-venv.ps1 -PythonVersion "${{ matrix.python-version }}"' in windows
    assert windows.count("$env:CI_PYTHON -m") == 2
