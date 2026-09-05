# Local CI Parity

Status: **Active** — shipped by H3 of
[FOUNDATION_HARDENING_PLAN.md](FOUNDATION_HARDENING_PLAN.md), closes issue #63.

`scripts/local_ci.sh` runs the same gates as `.github/workflows/ci.yml`, with the
same pinned toolchain, so a developer or agent learns that local and CI disagree
*before* pushing.

Two failures on 2026-07-22 motivated this. H1 (#82) was a test that failed on the
local 3.12.3 interpreter while CI stayed green. H2b (#85) was the same gate set
resolving to different tool versions on different days. Both were invisible until
someone happened to run the right command in the right environment.

## Run the gates

```bash
./scripts/local_ci.sh
```

That is the full CI verdict: ruff (`E4,E7,E9,F,B,I,UP,C4`), mypy over
`agent_sessions tools tests` with `disallow_untyped_defs`, and the test suite
with coverage against a `--cov-fail-under=92` floor, in a
throwaway virtualenv built from `constraints-dev.txt`. Roughly 60-90s cold
(mostly `pip install`), ~20s of actual gate time.

| Option | Effect |
| --- | --- |
| `--lint-only` | ruff + mypy only. Fast inner loop, **not** the CI verdict — the script says so and prints the skipped command. |
| `--venv DIR` | Reuse a persistent venv instead of a throwaway one. Much faster on repeat runs. The reused environment is **additive** — pip installs the pins but never prunes, so a package left over from an earlier experiment can mask a missing dependency CI would fail on. Only the default throwaway mode is a clean-checkout verdict. `DIR` must be gitignored (`.venv/` and `.venv-local-ci/` are); the script warns if it is inside the repo and is not. A relative `DIR` resolves against your current directory. If `DIR` already exists and its interpreter's minor version differs from the base interpreter, the script aborts rather than report one version while testing another. |
| `--python BIN` | Base interpreter for the venv. Also `PYTHON=`. |
| `-h`, `--help` | Usage. |

```bash
./scripts/local_ci.sh --lint-only            # ~5s after the first run
./scripts/local_ci.sh --venv .venv-local-ci  # reuse the environment
PYTHON=python3.13 ./scripts/local_ci.sh      # match the CI interpreter
```

There is no `--fast` / `--full` split: the full set costs seconds here, and a
default that skips the test gate would mean "local green" no longer implies "CI
green", which is the exact failure this script exists to prevent.

### What it does not cover

**One local interpreter, two CI legs.** CI runs Python 3.13 on Linux and native
Windows. The script prints when the local interpreter does not match that
guarded workflow matrix. The package retains its Python 3.11+ runtime floor for
existing installations, but versions below 3.13 are no longer CI-backed.

**Windows now runs on both forges (supersedes H6/D7's GitHub-only decision).**
The Windows legs are unconditional. They previously carried
`if: github.server_url == 'https://github.com'` on the premise that every
registered Forgejo runner was Linux. That premise was false — Forgejo has
`avis-msi-win-runner` and `avis-surface-win-runner`, both advertising
`windows-latest` — and because GitHub Actions is disabled on the backup mirror
under the Forgejo-primary invariant, the condition was never true on *either*
forge. The result was the worst of both worlds: the native-Windows legs
executed nowhere, while Forgejo's skipped-to-success status mapping reported
`CI / test (py 3.11, windows-latest) — success` on every pull request. Adding a
`.forgejo/workflows/` file is still *not* the answer and the drift guard still
rejects it (D7).

The native-Windows job deliberately avoids reusable actions. One registered
Windows runner cannot clone action repositories with its current runner/Git
combination, and Forgejo's Windows execution does not reliably apply a
composite action's PATH update between the action's inner steps. The workflow
therefore performs an authenticated, exact-SHA checkout without persisting the
short-lived token, then `scripts/ci-python-venv.ps1` selects the requested
tool-cache interpreter and exposes the venv's interpreter explicitly as
`CI_PYTHON`. The install and test commands invoke that exact executable rather
than trusting ambient PATH state.

**Linux `setup-python` on a read-only hosted toolcache.** Self-hosted Forgejo
`ci-heavy` / `ci-light` runners sometimes remount `/opt/hostedtoolcache`
read-only. `actions/setup-python@v6` then fails with `mkdir: cannot create
directory ‘/opt/hostedtoolcache/Python’: Read-only file system` before any repo
gate runs (measured 2026-09-03 on #169). Every Linux job that still uses
`setup-python` first runs `scripts/ci-writable-python-toolcache.sh`, which
points `AGENT_TOOLSDIRECTORY` and `RUNNER_TOOL_CACHE` at `$RUNNER_TEMP` and
clears `PIP_REQUIRE_VIRTUALENV` so the action's post-download pip upgrade can
run outside a venv. That step is CI-only; `local_ci.sh` mirrors the `run:`
line for drift detection and does not execute it.

### The `ci-gate` job — read this one, not the individual checks

**Forgejo reports a SKIPPED job as `success` in the commit-status API.** A job
carrying `if:` therefore renders a green check even when it never executed, and
the combined status stays green. No individual status context can distinguish
"passed" from "never ran", which is precisely how the Windows gap above stayed
invisible for weeks.

`ci-gate` is the one context that can tell the difference. It depends on every
other job, runs with `if: ${{ always() }}` so a failed dependency cannot skip
it into a false pass, and calls `scripts/ci-gate.sh` to assert on
`needs.<job>.result` — where `skipped` is a distinct value from `success` and is
rejected. Branch protection should require **`ci-gate` and nothing else**.

The drift guard enforces this structurally, so it cannot rot: it fails if
`ci-gate` disappears, if it loses `always()`, if any job is missing from its
`needs:` list, or if a job is in `needs:` but its result is never passed to the
assertion. Those checks are scoped to the `ci-gate` block, so a similarly named
key on another job cannot satisfy them. Job-level `if:` is permitted for
`ci-gate` alone.

A genuinely optional leg can be declared with
`scripts/ci-gate.sh --allow-skipped <job>`; the skip is then still surfaced as
`NOT RUN` and the gate refuses to claim full coverage. Prefer not needing it.

**Shell scripts are not linted.** `scripts/` contains `local_ci.sh`,
`daily-export.sh`, `pre-push` and `daily-export.ps1` — no Python, so ruff has
nothing to check there and the ruff gate's clean verdict says nothing about them.
Shell linting is deliberately out of scope: `shellcheck` is a system binary, not
a pinnable Python dependency, so adding it would either break the exact-`==`-pin
rule in `constraints-dev.txt` or introduce an unpinned tool whose verdict drifts
with whatever the runner image ships — the precise failure H2b existed to stop.
It would also not fit this script's `python -m <tool>` gate contract, so the
`run:` line would be expected-but-unexecutable locally, weakening the parity H3
provides. `# shellcheck disable=` directives already in `local_ci.sh` are for
humans running shellcheck by hand.

**The working tree, not the commit.** The script lints and tests whatever is
checked out, including untracked and uncommitted files. CI runs the committed
tree from `actions/checkout`. So an untracked module that tests import makes
local green and CI red, and an uncommitted fix can hide a red commit. The script
prints a note when the tree is dirty. The pre-push hook closes this gap for
pushes specifically — see [below](#the-pre-push-hook).

**The pinned set, not the whole dependency closure.** `constraints-dev.txt` pins
the gate tools plus the transitives whose behaviour shows up in gate output;
`mypy_extensions`, `typing_extensions`, `pathspec`, `pygments`, `pillow` and pip
itself still float. Same-toolchain is a bounded claim, and the file's header says
so.

**Platform.** The script needs bash ≥ 4 (it checks, and says so on macOS's bash
3.2) and works with both POSIX (`bin/python`) and Windows (`Scripts/python.exe`)
venv layouts, but it is exercised on Linux/WSL only.

The venv is thrown away after every run unless `--venv` is passed, so the verdict
reflects a clean checkout rather than whatever happens to be installed. Tools are
always invoked as `<venv>/bin/python -m <tool>`, never as a bare `ruff` or
`pytest` from `PATH`, which on a machine with conda or a `~/.local` install would
silently be a different interpreter.

## The drift guard

The script is only useful while it still mirrors CI, so it checks that first,
before building anything, and exits 1 on any mismatch. It fails on *absence* as
well as on difference — a guard that passes when it cannot find what it is
looking for is worse than no guard.

It verifies that:

- `.github/workflows/ci.yml` exists and is the **only** workflow file, and that
  `.forgejo/workflows/` does not exist (D7: Forgejo executes `.github/workflows/`
  directly, so a second file would be an ungated gate set);
- the multiset of `run:` commands in the workflow is exactly the set the script
  executes — this catches a changed flag, an added or removed job, and a dropped
  `-c constraints-dev.txt`, not just version pins;
- the workflow's Python matrix still lists the versions the script reports on;
- the workflow's **OS matrix and `include:` legs** are unchanged — the closing
  "CI also runs this set on …" line is generated from them, so deleting a
  Windows leg trips the guard instead of leaving the script claiming coverage CI
  no longer provides. Write each `include:` entry with `os:` **before**
  `python-version:` — the guard pairs them in that order and silently drops an
  entry written the other way round;
- no `if:`, `continue-on-error:` or `env:` key appears in the workflow. None
  exists today, and each can disable or alter a gate while leaving its `run:`
  line byte-identical — a `run:` line only means "enforced gate" while nothing
  neuters it. Adding one legitimately means updating this guard deliberately;
- `constraints-dev.txt` exists and every entry is an exact `==` pin, checked
  after stripping comments so `requests>=2.0  # ==pinned` cannot smuggle a loose
  pin past an unanchored match.

**Known blind spots.** The guard compares gate commands, the matrices, the
disabling keys above, and pin exactness. It does *not* compare workflow triggers
(`on:`), action versions (`actions/setup-python@v5`), `permissions:`,
`concurrency:`, or step ordering — CI could stop running on pull requests and the
guard would still say OK. Those are deliberately out of scope: they change
*when* CI runs, not *what* it runs, which is what this script mirrors.

Tool *versions* are deliberately not written into the script. It installs with
`-c constraints-dev.txt` exactly as CI does, so the pins are consumed, never
transcribed, and cannot drift. Bumping a pin is a one-line change to that file
and needs no change here.

Example failure:

```
local_ci: DRIFT DETECTED — the gate commands in .github/workflows/ci.yml do not match this script.
  In CI but not run locally:
    python -m pytest --cov=agent_sessions --cov-report=term-missing --cov-fail-under=95
  Run locally but no longer in CI:
    python -m pytest --cov=agent_sessions --cov-report=term-missing --cov-fail-under=92

This script no longer mirrors .github/workflows/ci.yml. Update the gate arrays at the
top of scripts/local_ci.sh (and docs/LOCAL_CI.md) to match, or revert
the workflow change. ...
```

The fix is to update the `ci_*` arrays at the top of `scripts/local_ci.sh`. They
are the single source of truth: the guard compares them to the workflow and the
gates execute them, so there is no second copy to forget.

## The pre-push hook

`scripts/pre-push` runs the gates on `git push` and aborts the push if they fail.
It is opt-in and never installs itself. It never writes to tracked files, the
index, the working tree, or git config; it does create a temporary detached
worktree (removed on exit, see below), and the gate script it runs writes
gitignored build artifacts (`*.egg-info/`, `.coverage`).

### It gates the pushed commits, not the checkout

Git pushes *commits*. The working tree may be ahead of them, behind them, or
unrelated (`git push origin feat:feat` from another branch). Gating the checkout
gave both wrong answers: a commit whose breakage had been undone in the working
tree reached the remote under an "all gates passed" verdict, and unrelated dirty
files blocked a push of otherwise-clean commits.

So the hook checks the pushed sha:

- if the working tree is clean **and** `HEAD` is that sha, it gates the checkout
  in place (the fast, common path — the checkout provably *is* the commit);
- otherwise it runs `git worktree add --detach` at that exact sha, runs the gates
  there, and removes the worktree on exit (including on failure).

If a pushed commit predates `scripts/local_ci.sh`, the hook says so and refuses
rather than pretend it gated something; `git push --no-verify` is the escape.

### Install

Hooks are not tracked by git, so this is once per clone. On Linux/WSL/macOS,
symlink it so it cannot go stale:

```bash
ln -s ../../scripts/pre-push .git/hooks/pre-push
```

On Windows without developer mode (symlinks unavailable), copy it instead, and
re-copy after any change to `scripts/pre-push`:

```powershell
Copy-Item scripts\pre-push .git\hooks\pre-push
```

Both scripts are bash and need bash ≥ 4, so on Windows they run under WSL or Git
Bash, not `cmd`/PowerShell directly. `local_ci.sh` handles the Windows venv
layout (`Scripts\python.exe`) as well as the POSIX one, but the supported and
exercised path is WSL/Linux — if you push from PowerShell, run
`./scripts/local_ci.sh` inside WSL instead of relying on the hook.

**Decision: `.git/hooks` over `core.hooksPath`.** `git config core.hooksPath
scripts` would also work and stays live automatically, but it *replaces* the
hooks directory for the whole clone, silently disabling any other
`.git/hooks/*` entry the machine already relies on. The symlink gets the same
freshness without that side effect. Uninstall is `rm .git/hooks/pre-push`.

### Bypasses

In increasing order of "I know what I am doing":

1. **Documentation-only push** — skipped automatically. The classifier is a
   positive allowlist (`*.md`, `*.markdown`, `*.rst`, `LICENSE`, `COPYING`,
   `NOTICE`); anything unrecognised runs the gates, and an empty file list also
   runs them. `constraints-dev.txt`, `pyproject.toml`, `.github/workflows/*`,
   `scripts/*`, `agent_sessions/*`, `tools/*`, and `tests/*` are therefore never
   skipped. This is safe here only because CI has no docs gate (no link check, no
   markdown lint) and no test reads a tracked `.md` file — revisit it if that
   changes.
2. **`SKIP_LOCAL_CI=1 git push`** — skip the gates for one push.
3. **`git push --no-verify`** — skip every hook.

The hook is a pre-filter, not a substitute for CI or for the `AGENTS.md`
PR → review → LGTM → merge flow.

### How it decides what changed

Git feeds the hook `<local ref> <local sha> <remote ref> <remote sha>` on stdin,
one line per pushed ref, and the hook diffs those ranges. (`git diff --cached` is
wrong at push time — nothing is staged.) For a branch the remote has not seen, it
derives the base from the remote's own refs rather than a hardcoded
`origin/main`, because this repo's primary remote is Forgejo (`forge`). Branch
deletions are not gated.

Every step of this **fails closed**. If a range cannot be computed — the remote
sha is not in this clone, which happens on any force-push after someone else
moved the branch — the hook runs the gates instead of treating it as "no files
changed". That inversion was a real hole: an undiffable code ref contributed zero
files, a docs-only sibling ref in the same push then classified the whole push as
documentation, and the code reached the remote ungated under a reassuring skip
message.

`tests/test_pre_push_hook.py` covers the classifier, each ref case, the
multi-ref/unresolvable-sha shape, and the commit-not-checkout gating; the
classifier is directly callable for testing:

```bash
printf 'README.md\n' | LOCAL_CI_CHECK_FILES=1 scripts/pre-push   # -> skip
```
