"""Tests for the pre-push hook's skip heuristic and pushed-file detection (H3).

The hook decides whether a push is gated. A false "skip" is the failure that
matters — it lets a red commit reach the remote — so the classifier is tested
directly through its ``LOCAL_CI_CHECK_FILES`` seam, and the ref-protocol parsing
is tested end to end against a throwaway repo with a stubbed gate script.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "scripts" / "pre-push"

BASH = shutil.which("bash")
GIT = shutil.which("git")

requires_bash = pytest.mark.skipif(BASH is None, reason="bash is not available on this platform")
requires_git = pytest.mark.skipif(BASH is None or GIT is None, reason="bash and git are required")

ZERO = "0" * 40


def classify(paths: list[str]) -> str:
    assert BASH is not None
    result = subprocess.run(
        [BASH, str(HOOK)],
        input="".join(f"{path}\n" for path in paths),
        capture_output=True,
        text=True,
        env={**os.environ, "LOCAL_CI_CHECK_FILES": "1"},
        check=True,
    )
    return result.stdout.strip()


@requires_bash
class TestDocsOnlyClassifier:
    @pytest.mark.parametrize(
        "paths",
        [
            ["README.md"],
            ["docs/LOCAL_CI.md", "docs/AUTOMATION.md"],
            ["LICENSE"],
            ["docs/notes.rst"],
        ],
    )
    def test_documentation_skips(self, paths: list[str]) -> None:
        assert classify(paths) == "skip"

    @pytest.mark.parametrize(
        "paths",
        [
            ["agent_sessions/cli.py"],
            ["tests/test_cli.py"],
            ["tools/agent_archive.py"],
            ["pyproject.toml"],
            # Gate inputs that a naive "*.txt is docs" rule would wave through.
            ["constraints-dev.txt"],
            [".github/workflows/ci.yml"],
            ["scripts/local_ci.sh"],
            ["scripts/pre-push"],
            # A docs/ directory does not make a .py file documentation.
            ["docs/tools/generate.py"],
            # One code file among many docs still runs the gates.
            ["README.md", "docs/a.md", "agent_sessions/utils.py"],
        ],
    )
    def test_code_runs_the_gates(self, paths: list[str]) -> None:
        assert classify(paths) == "run"

    def test_empty_input_runs_the_gates(self) -> None:
        # Fail-safe: an unknown file set is never provably docs-only.
        assert classify([]) == "run"


def git(repo: Path, *args: str) -> str:
    assert GIT is not None
    result = subprocess.run(
        [GIT, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path) -> Path:
    """A repo whose scripts/local_ci.sh is a stub, so the gate is observable."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(HOOK, repo / "scripts" / "pre-push")
    stub = repo / "scripts" / "local_ci.sh"
    stub.write_text("#!/usr/bin/env bash\necho RAN_LOCAL_CI\n", encoding="utf-8")
    stub.chmod(0o755)

    git(repo.parent, "init", "--quiet", str(repo))
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("start\n", encoding="utf-8")
    git(repo, "add", "README.md", "scripts/local_ci.sh", "scripts/pre-push")
    git(repo, "commit", "--quiet", "-m", "initial")
    return repo


def run_hook(repo: Path, stdin: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(
        [BASH, "scripts/pre-push", "origin", str(repo)],
        cwd=repo,
        input=stdin,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


@requires_git
class TestPushedFileDetection:
    def test_existing_branch_range_gates_code(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        base = git(repo, "rev-parse", "HEAD")
        (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "code.py")
        git(repo, "commit", "--quiet", "-m", "code")
        head = git(repo, "rev-parse", "HEAD")

        result = run_hook(repo, f"refs/heads/main {head} refs/heads/main {base}\n")

        assert result.returncode == 0
        assert "RAN_LOCAL_CI" in result.stdout

    def test_existing_branch_range_skips_docs(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        base = git(repo, "rev-parse", "HEAD")
        (repo / "README.md").write_text("changed\n", encoding="utf-8")
        git(repo, "add", "README.md")
        git(repo, "commit", "--quiet", "-m", "docs")
        head = git(repo, "rev-parse", "HEAD")

        result = run_hook(repo, f"refs/heads/main {head} refs/heads/main {base}\n")

        assert result.returncode == 0
        assert "RAN_LOCAL_CI" not in result.stdout
        assert "documentation-only" in result.stdout

    def test_new_branch_without_remote_ref_gates(self, tmp_path: Path) -> None:
        # No remote refs exist, so the hook cannot bound the range and must not
        # guess its way into a skip.
        repo = make_repo(tmp_path)
        (repo / "README.md").write_text("changed\n", encoding="utf-8")
        git(repo, "add", "README.md")
        git(repo, "commit", "--quiet", "-m", "docs")
        head = git(repo, "rev-parse", "HEAD")

        result = run_hook(repo, f"refs/heads/feat {head} refs/heads/feat {ZERO}\n")

        assert result.returncode == 0
        assert "RAN_LOCAL_CI" in result.stdout

    def test_branch_deletion_is_not_gated(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)

        result = run_hook(repo, f"(delete) {ZERO} refs/heads/gone {ZERO}\n")

        assert result.returncode == 0
        assert "RAN_LOCAL_CI" not in result.stdout
        assert "nothing to gate" in result.stdout

    def test_skip_env_var_bypasses(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        base = git(repo, "rev-parse", "HEAD")
        (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "code.py")
        git(repo, "commit", "--quiet", "-m", "code")
        head = git(repo, "rev-parse", "HEAD")

        result = run_hook(
            repo,
            f"refs/heads/main {head} refs/heads/main {base}\n",
            env={"SKIP_LOCAL_CI": "1"},
        )

        assert result.returncode == 0
        assert "RAN_LOCAL_CI" not in result.stdout

    def test_red_gate_aborts_the_push(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        (repo / "scripts" / "local_ci.sh").write_text("#!/usr/bin/env bash\nexit 3\n", encoding="utf-8")
        base = git(repo, "rev-parse", "HEAD")
        (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "code.py", "scripts/local_ci.sh")
        git(repo, "commit", "--quiet", "-m", "code")
        head = git(repo, "rev-parse", "HEAD")

        result = run_hook(repo, f"refs/heads/main {head} refs/heads/main {base}\n")

        assert result.returncode == 3

    def test_unresolvable_remote_sha_forces_the_gates(self, tmp_path: Path) -> None:
        # The dangerous shape: one ref whose remote sha is not in this clone (any
        # force-push after someone else moved the branch) plus a docs-only
        # sibling ref. Treating the undiffable ref as "no files changed" made the
        # whole push classify as documentation and reach the remote ungated.
        repo = make_repo(tmp_path)
        code_base = git(repo, "rev-parse", "HEAD")
        (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "code.py")
        git(repo, "commit", "--quiet", "-m", "code")
        code_head = git(repo, "rev-parse", "HEAD")
        (repo / "README.md").write_text("changed\n", encoding="utf-8")
        git(repo, "add", "README.md")
        git(repo, "commit", "--quiet", "-m", "docs")
        docs_head = git(repo, "rev-parse", "HEAD")

        missing = "1" * 40
        result = run_hook(
            repo,
            f"refs/heads/code {code_head} refs/heads/code {missing}\n"
            f"refs/heads/docs {docs_head} refs/heads/docs {code_base}\n",
        )

        assert result.returncode == 0
        assert "documentation-only" not in result.stdout
        assert "RAN_LOCAL_CI" in result.stdout


@requires_git
class TestGatesThePushedCommit:
    """git pushes commits; the working tree is not necessarily either of them."""

    def test_committed_content_is_gated_not_the_working_tree(self, tmp_path: Path) -> None:
        # A red commit whose breakage has been undone in the working tree used to
        # sail through with an "all gates passed" verdict.
        repo = make_repo(tmp_path)
        (repo / "scripts" / "local_ci.sh").write_text(
            "#!/usr/bin/env bash\necho RAN_LOCAL_CI\n"
            'grep -q BROKEN code.py 2>/dev/null && { echo SAW_BROKEN; exit 3; }\nexit 0\n',
            encoding="utf-8",
        )
        git(repo, "add", "scripts/local_ci.sh")
        git(repo, "commit", "--quiet", "-m", "gate stub")
        base = git(repo, "rev-parse", "HEAD")

        (repo / "code.py").write_text("BROKEN\n", encoding="utf-8")
        git(repo, "add", "code.py")
        git(repo, "commit", "--quiet", "-m", "red commit")
        head = git(repo, "rev-parse", "HEAD")

        # "Fix" it in the working tree only; the commit stays red.
        (repo / "code.py").write_text("fine\n", encoding="utf-8")

        result = run_hook(repo, f"refs/heads/main {head} refs/heads/main {base}\n")

        assert "SAW_BROKEN" in result.stdout
        assert result.returncode == 3

    def test_clean_checkout_at_the_pushed_sha_runs_in_place(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        base = git(repo, "rev-parse", "HEAD")
        (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "code.py")
        git(repo, "commit", "--quiet", "-m", "code")
        head = git(repo, "rev-parse", "HEAD")

        result = run_hook(repo, f"refs/heads/main {head} refs/heads/main {base}\n")

        assert result.returncode == 0
        assert "clean checkout is that commit" in result.stdout
        assert "RAN_LOCAL_CI" in result.stdout

    def test_temporary_worktree_is_removed(self, tmp_path: Path) -> None:
        repo = make_repo(tmp_path)
        base = git(repo, "rev-parse", "HEAD")
        (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "code.py")
        git(repo, "commit", "--quiet", "-m", "code")
        head = git(repo, "rev-parse", "HEAD")
        (repo / "dirty.py").write_text("y = 2\n", encoding="utf-8")  # forces the worktree path

        result = run_hook(repo, f"refs/heads/main {head} refs/heads/main {base}\n")

        assert result.returncode == 0
        assert "temporary worktree" in result.stdout
        assert git(repo, "worktree", "list").count("\n") == 0


@requires_bash
def test_hook_is_checked_out_with_lf_endings() -> None:
    # A CRLF hook fails with "bad interpreter" on Linux/WSL; .gitattributes pins
    # it, and this test proves the pin is in effect on this checkout.
    assert b"\r\n" not in HOOK.read_bytes()
