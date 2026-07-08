# Agent Sessions

Private archive for coding-agent sessions across machines and tools.

This repo is meant to hold portable Markdown/PDF exports, plus the tooling used
to recreate them from local agent stores. Raw logs are supported but ignored by
Git by default because they can be large and may contain credentials, file
contents, or tool outputs.

## Current Importers

- Codex Windows: local and archived JSONL sessions
- Claude Code Windows/WSL: project JSONL sessions
- Gemini Antigravity Windows: transcript JSONL files
- Grok WSL: `chat_history.jsonl` files
- DeepSeek V4 VS Code extension: request dump prompts from VS Code globalStorage

VS Code Copilot Chat and Z.AI/ZAI locations are discovered and documented, but
the first exporter treats them as source inventory unless transcript files are
present in known locations.

Default sources live in `config/default_sources.toml`. Copy
`sources.example.toml` to `sources.toml` for local machine overrides.

## Quick Start

```powershell
python -m pip install -e ".[dev]"
python .\tools\agent_archive.py discover --write docs\DISCOVERY.md
python .\tools\agent_archive.py status
python .\tools\agent_archive.py export --all
```

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
[docs/BASELINE_LOOP_CLOSURE.md](docs/BASELINE_LOOP_CLOSURE.md). The newer
knowledge and replay tracker is complete in
[docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md](docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md),
with current health and follow-ups summarized in
[docs/WORK_AUDIT_2026-07-08.md](docs/WORK_AUDIT_2026-07-08.md).

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
