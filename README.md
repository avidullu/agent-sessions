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
> **Agent-assisted setup?** → [Agent-Assisted Setup](#agent-assisted-setup) (give any capable agent a prompt; it sets up the archive on a new machine)  
> **Questions?** → [FAQ](docs/FAQ.md)  
> **What comes after export?** → [Review lessons](docs/BASELINE_USER_GUIDE.md)\
> **Where is this going?** → [Product direction and code map](docs/PRODUCT_DIRECTION.md)\
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

Run `agent-archive init` in your private workspace to create `sources.toml` from packaged defaults.
Review the source paths before exporting; a source checkout is not required.

## Quick Start

```bash
# Install
pip install agent-session-hub

# Confirm which installed release you are running
agent-archive --version

# Create a private workspace (init requires hub 0.3.0 or newer)
mkdir my-agent-archive
cd my-agent-archive
agent-archive init
# For VS Code: set agentSessionRouter.outputDir to the directory printed by init.
# Auto-export is opt-in; otherwise use the router's Export All Sessions command.

# Discover sessions
agent-archive discover --write docs/DISCOVERY.md

# Export to Markdown
agent-archive export --all

# Check status
agent-archive status

# Inspect whether this machine can host the daily local-only routine
agent-archive --repo-root . routine status
```

Query local source-control provenance without storing PR or session bodies:

```bash
agent-archive provenance --forgejo-url https://forge.example.test sync \
  --token-file ~/.config/forgejo/provenance.token \
  --identity-policy /path/to/agent-identities.v1.json \
  --repo Example/project --pr 123
agent-archive provenance --forgejo-url https://forge.example.test who \
  --repo Example/project --pr 123
```

The rebuildable SQLite index distinguishes observed Forgejo actors, Git
identity/signature evidence, unverified co-author trailers, and explicit
owner/session attestations. See
[Forgejo agent provenance](docs/FORGEJO_AGENT_PROVENANCE.md).

See [Getting Started](docs/GETTING_STARTED.md) for full setup including the VS Code extension, PDF export, and daily automation.

**Prefer to let an agent do the setup?** See [Agent-Assisted Setup](#agent-assisted-setup) — a prompt that lets a capable agent install the hub, initialize a private workspace, check collection, and help produce a first archive without cloning the product repo.

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

`export --all` writes Markdown archive artifacts and updates the local catalog:

- `archive/**/*.md`
- `archive/index.jsonl`
- `archive/INDEX.md`

These generated files are ignored when untracked so a public product clone does
not accidentally publish personal metadata. An existing tracked private catalog
continues to be tracked; bootstrap a new private catalog deliberately with
`git add -f archive/index.jsonl archive/INDEX.md`.

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

1. Install `agent-session-hub` in an isolated Python environment and check
   `agent-archive --version`. This setup needs 0.3.0 or newer. If that version
   is not published yet, report that instead of silently switching to source.
2. Choose a private workspace outside the product source repo. Run
   `agent-archive init` there; preserve any existing configuration.
3. Review sources.toml with me before reading or exporting personal sessions.
   For VS Code, explain how to set agentSessionRouter.outputDir to the archive
   directory printed by init. Auto-export is opt-in.
4. After approval, run `agent-archive discover` and `agent-archive status`.
   Explain missing roots, inventory-only sources and unknown freshness without
   claiming that a watcher is active based on the hub's status alone.
5. Ask before the first export, PDF generation, scheduling, or private catalog
   sync. For an approved Markdown export use `agent-archive export --all`.
   Do not add --pdf or --copy-raw unless separately requested.
6. Check the resulting Markdown and collection health. Summarize the installed
   version, sources, indexed sessions, new/changed files, archive location,
   collection problems, and what remains manual.
7. If I want to review lessons, follow docs/BASELINE_USER_GUIDE.md from the
   published source. Start with a dry run; candidate suggestions are not my
   approved instructions. Do not invent useful guardrails for an empty archive.

Keep transcripts, catalogs and sources.toml local. Do not stage or push them to
the public product repo. No scheduling, upload, instruction rewrite or PR merge
without my explicit approval for that action.
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

See [docs/AUTOMATION.md](docs/AUTOMATION.md) for machine-readable routine
discovery and scheduled export (local-only
primary host via `scripts/local-export` / `install-local-export-schedule`, or
private catalog sync via `daily-export`) and
[docs/MULTI_MACHINE.md](docs/MULTI_MACHINE.md) for how indexes converge across
computers. For a step-by-step manual checklist, see
[docs/NEW_MACHINE_SETUP.md](docs/NEW_MACHINE_SETUP.md).

## Adding Agents

1. Add a source entry in packaged `agent_sessions/default_sources.toml` or local `sources.toml`.
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

Start with the [baseline user guide](docs/BASELINE_USER_GUIDE.md) for an exact-run
review, feedback, promotion and calibration walkthrough. These are local derived
artifacts, not automatic writes into another agent's instructions or memory.

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
browsing, live capture, and optional vendor runtime memory are delegated to
external tools where they are already stronger. Curated instructions and
project memory belong in an owner-chosen control plane, not in this archive;
the only write from sessions into that plane is an owner-attested promote.
See [docs/COMPOSE_STACK.md](docs/COMPOSE_STACK.md) and
[docs/XDSYNC_BOUNDARY.md](docs/XDSYNC_BOUNDARY.md).

Daily export automation (local-only schedule or private catalog push) is
documented in [docs/AUTOMATION.md](docs/AUTOMATION.md). Multi-machine indexing is
documented in [docs/MULTI_MACHINE.md](docs/MULTI_MACHINE.md).

## Reusable Plugins

This repo also hosts a Claude Code plugin marketplace (`agent-sessions-tools`).
Install the `pr-review-loop` PR-reviewer plugin from any session:

```shell
/plugin marketplace add avidullu/agent-sessions
/plugin install pr-review-loop@agent-sessions-tools
```

See [plugins/pr-review-loop/README.md](plugins/pr-review-loop/README.md).

## Other Machines

Install the hub and initialize a separate local workspace on each machine.
Session bodies and catalogs stay local by default. Only opt into catalog sync
against your own private remote; do not push session data to the public product repo.
See [docs/NEW_MACHINE_SETUP.md](docs/NEW_MACHINE_SETUP.md).
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
