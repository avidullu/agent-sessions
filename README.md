# Agent Sessions

[![CI](https://github.com/avidullu/agent-sessions/actions/workflows/ci.yml/badge.svg)](https://github.com/avidullu/agent-sessions/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/agent-session-hub?label=PyPI)](https://pypi.org/project/agent-session-hub/)
[![VS Code extension](https://img.shields.io/visual-studio-marketplace/v/avidullu.agent-session-router?label=VS%20Code%20extension)](https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router)

**Local-first, multi-agent coding session archive.** Discover, export, and
baseline your AI coding sessions across Claude Code, Codex CLI, Gemini,
DeepSeek, Grok, and VS Code agents (via the companion
[router extension](https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router)).

> The Python hub installs as [`agent-session-hub`](https://pypi.org/project/agent-session-hub/) on PyPI; the VS Code companion is
> [`avidullu.agent-session-router`](https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router) on the Marketplace
> (`code --install-extension avidullu.agent-session-router`).

> **New here?** → [Getting Started](docs/GETTING_STARTED.md) (5-minute guide)
> **Questions?** → [FAQ](docs/FAQ.md)
> **Want to contribute?** → [CONTRIBUTING.md](CONTRIBUTING.md)

## Supported Agents

> **Note:** This tool has been manually tested on **Windows, WSL, and Ubuntu**. macOS
> support is provided through the same code paths but has not been validated by the
> developer (who does not own a Mac). If you hit macOS-specific issues, please file a
> bug — PRs welcome!

| Agent | Platform | Via |
|-------|----------|-----|
| Claude Code | Windows, macOS, Linux, WSL | Direct Python importer |
| Codex CLI | Windows, macOS, Linux | Direct Python importer |
| Gemini Antigravity | Windows, macOS | Direct Python importer |
| Grok | WSL, Linux | Direct Python importer |
| DeepSeek V4 | VS Code (all platforms) | Direct Python importer |
| GitHub Copilot Chat | VS Code (all platforms) | [Router extension](https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router) |
| Continue, Cline, Cody, Aider, Tabby | VS Code (all platforms) | [Router extension](https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router) |

Configure sources in `sources.toml` (copy from `sources.example.toml`). Platform-specific examples included for Windows, macOS, Linux, and WSL.

## Quick Start

```bash
# Install
pip install agent-session-hub

# Discover sessions
agent-archive discover --write docs/DISCOVERY.md

# Export to Markdown
agent-archive export --all

# Check status
agent-archive status
```

See [Getting Started](docs/GETTING_STARTED.md) for full setup including the VS Code extension, PDF export, and daily automation.

Optional PDF output:

```powershell
python .\tools\agent_archive.py export --all --pdf
```

Optional raw backups:

```powershell
python .\tools\agent_archive.py export --all --copy-raw
```

Raw files land under `raw/`, which is ignored by Git unless you intentionally
force-add it.

### Expected Outputs

`discover --write docs\DISCOVERY.md` refreshes the local source inventory:

- configured source roots, whether each root exists, and matching file counts;
- sample files per source;
- inventory-only sources such as Copilot/ZAI storage locations, even when they
  are not exportable transcript sources yet.

`status` prints archive freshness and convergence signals:

- indexed records, visible configured files, new files, and changed files;
- indexed records not visible from this machine, preserved from other machines;
- source counts and inferred origin environments.

`export --all` writes Markdown archive artifacts and updates the shared catalog:

- `archive/**/*.md`
- `archive/index.jsonl`
- `archive/INDEX.md`

`export --all --pdf` also writes `archive/**/*.pdf` when `reportlab` is
installed. The `.[dev]` install includes `reportlab`; to check a minimal
environment, run:

```powershell
python -c "import reportlab; print('reportlab ok')"
```

If PDF support is missing, Markdown export still works. The CLI will report that
PDF export requires `reportlab`.

Some configured sources are intentionally inventory-only. A message like this is
expected unless transcript files exist in supported locations:

```text
Skipped sources without extractors:
- copilot-vscode-windows-inventory (inventory)
- copilot-vscode-wsl-ubuntu-inventory (inventory)
- zai-vscode-wsl-ubuntu-inventory (inventory)
```

After a real export, review only the intended generated paths:

```powershell
git status --short archive/ docs/DISCOVERY.md
```

Stage explicit paths only. Do not commit `sources.toml`, `raw/`, or unrelated
files.

## Verify Changes Before Opening A PR

Run CI's gates locally, with CI's pinned toolchain, in a throwaway venv:

```bash
./scripts/local_ci.sh
```

That runs `ruff check`, `mypy`, and the test suite with coverage — the same
commands as `.github/workflows/ci.yml` — and refuses to run at all if the script
has drifted from the workflow. Use `--lint-only` for a fast inner loop, but note
it is not the CI verdict.

### Automatic Enforcement On `git push`

`scripts/pre-push` is an opt-in git hook that runs the gates and aborts a push
that would go red. Install it once per clone:

```bash
ln -s ../../scripts/pre-push .git/hooks/pre-push
```

The hook gates the commits being pushed, not whatever happens to be checked out.
Documentation-only pushes are skipped automatically; `SKIP_LOCAL_CI=1 git push`
and `git push --no-verify` are the explicit bypasses. Full details, including the
drift guard, the parity limits, and the Windows/WSL install path, are in
[docs/LOCAL_CI.md](docs/LOCAL_CI.md).

## Agent-Assisted Setup

To set this up on a new computer with Codex, Claude, Gemini, Grok, DeepSeek, or
another capable local agent, give the agent this prompt from the machine you
want to add:

```text
Set up my private agent-sessions archive on this computer.

1. Clone or open the repo:
   https://github.com/avidullu/agent-sessions
   Pull with `git pull --ff-only` before reading files.
2. Install local tooling in a Python 3.11+ environment:
   `python -m pip install -e ".[dev]"`
3. Validate the repo and report results. Use POSIX-style paths in the prompt;
   PowerShell users may substitute `.\tools\...` and `docs\DISCOVERY.md` if
   they prefer:
   - `python -m pytest --cov=agent_sessions --cov-report=term-missing`
   - `python -m ruff check .`
   - `python -m mypy agent_sessions tools`
   - optional/informational: `python tools/agent_archive.py baseline eval --dry-run`
4. Discover local agent stores:
   - `python tools/agent_archive.py discover --write docs/DISCOVERY.md`
   - `python tools/agent_archive.py status`
   If defaults miss a local path, create or edit ignored `sources.toml`; do not
   commit `sources.toml`.
5. Ask me which sync mode I want before enabling it:
   - manual: export only when I ask
   - scheduled: daily Task Scheduler/cron export
   - triggered: filesystem watcher with debounce
   Ask separately whether to generate PDFs.
6. If I approve the first sync, run:
   `python tools/agent_archive.py export --all --pdf`
   Then stage only `archive/` changes. Push directly only if I explicitly
   approve this as a one-time archive sync; otherwise branch and open a PR.
7. Finish with a short setup report: validation status, agents discovered,
   total indexed sessions, new/changed files, origin environments, sync mode,
   and 1-2 promoted guardrails from `baseline/global/` or optional
   `baseline suggest --dry-run` output that show the value.

Do not commit raw logs, `sources.toml`, unrelated files, or merge PRs without
explicit approval scoped to that PR or project.
```

The final setup report should be plain enough to review at a glance:

```text
Repo validation:
- Tests/coverage:
- Ruff:
- Mypy:
- Baseline eval:

Local archive status:
- Agents/sources discovered:
- Indexed sessions:
- New files:
- Changed files:
- Origin environments:

Sync:
- Selected mode:
- PDF export:
- Last export/commit:

Value preview:
- Guardrail/pattern 1:
- Guardrail/pattern 2:
- Evidence breadcrumbs:
```

See [docs/AUTOMATION.md](docs/AUTOMATION.md) for scheduled export details and
[docs/MULTI_MACHINE.md](docs/MULTI_MACHINE.md) for how indexes converge across
computers. For a step-by-step manual checklist, see
[docs/NEW_MACHINE_SETUP.md](docs/NEW_MACHINE_SETUP.md).

## Adding Agents

1. Add a source entry in `config/default_sources.toml` or local `sources.toml`.
2. Add an extractor module under `agent_sessions/sources/`.
3. Register it with `@register("<kind>")`.
4. Run a dry export with `--source <kind> --limit 1 --dry-run`.

## Baseline Status And Follow-Ups

The original promote/publish/calibrate closure proof is documented in
[docs/archives/BASELINE_LOOP_CLOSURE.md](docs/archives/BASELINE_LOOP_CLOSURE.md). The newer
knowledge and replay tracker is complete in
[docs/archives/BASELINE_KNOWLEDGE_REPLAY_PLAN.md](docs/archives/BASELINE_KNOWLEDGE_REPLAY_PLAN.md),
with current health and follow-ups summarized in
[docs/archives/WORK_AUDIT_2026-07-08.md](docs/archives/WORK_AUDIT_2026-07-08.md).

Useful health checks:

```powershell
python .\tools\agent_archive.py baseline lint --dry-run
python .\tools\agent_archive.py baseline eval --dry-run
python .\tools\agent_archive.py baseline handoffs audit --dry-run
python .\tools\agent_archive.py baseline replay select --dry-run
```

## Engineering Baseline

Create or refresh the baseline scaffold:

```powershell
python .\tools\agent_archive.py baseline scaffold
```

Expected output: missing baseline folders and templates are created under
`baseline/`, including calibration examples and proposal scaffolding. Existing
files are preserved.

Generate reviewable candidate predictions from the archive:

```powershell
python .\tools\agent_archive.py baseline suggest
```

Expected output: a dated candidate report appears under `baseline/candidates/`,
with a matching `.predictions.json` sidecar, and the prediction ledger under
`baseline/metacognition/` is updated. Candidate reports are suggestions with
provenance and calibration hooks. Copy
`baseline/calibration/feedback.example.toml` to
`baseline/calibration/feedback.toml` to mark predictions as accepted, edited, or
rejected before the next run.

Summarize calibration feedback against the latest prediction sidecar:

```powershell
python .\tools\agent_archive.py baseline calibrate --feedback baseline\calibration\feedback.toml
```

Create a local evidence bundle for an authorized AI agent to draft proposals:

```powershell
python .\tools\agent_archive.py baseline bundle --focus badminton-highlight-indexer
```

## Compose Stack

This repo owns durable export and baseline generation. Search, Claude-specific
browsing, live capture, and runtime memory are delegated to external tools where
they are already stronger. See [docs/COMPOSE_STACK.md](docs/COMPOSE_STACK.md).

Daily export automation is documented in [docs/AUTOMATION.md](docs/AUTOMATION.md).
Multi-machine indexing is documented in [docs/MULTI_MACHINE.md](docs/MULTI_MACHINE.md).

## Reusable Plugins

This repo also hosts a Claude Code plugin marketplace (`agent-sessions-tools`).
Install the `pr-review-loop` PR-reviewer plugin from any session:

```shell
/plugin marketplace add avidullu/agent-sessions
/plugin install pr-review-loop@agent-sessions-tools
```

See [plugins/pr-review-loop/README.md](plugins/pr-review-loop/README.md).

## Other Machines

Clone this private repo on another machine, follow
[docs/NEW_MACHINE_SETUP.md](docs/NEW_MACHINE_SETUP.md), commit the new `archive/`
Markdown/PDF files, and push.
The archive index is merge-aware, so records from other machines remain in the
unified view when one machine exports only the local sources it can see.

If a machine has different usernames, WSL distribution names, or custom storage
paths, copy `sources.example.toml` to `sources.toml` and edit the roots. The
local `sources.toml` is ignored by Git.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for optional future importers and archive
automation ideas.

The engineering-baseline idea is sketched in
[docs/ENGINEERING_BASELINE.md](docs/ENGINEERING_BASELINE.md).
The current implementation plan is tracked in
[docs/BASELINE_PLANNING.md](docs/BASELINE_PLANNING.md).
