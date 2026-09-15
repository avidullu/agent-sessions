# Getting Started — Agent Sessions

A 5-minute guide to archiving your AI coding sessions.

## Prerequisites

- **Python 3.11+** — check with `python3 --version`
- **Git** — optional, only for source installation or explicitly chosen private sync
- One or more AI coding agents (Claude Code, Codex CLI, Gemini CLI, Grok, DeepSeek, or VS Code Copilot Chat via the router extension)

> **Platform note:** This tool has been manually tested on **Windows, WSL, and Ubuntu**.
> macOS should work through the same code paths but hasn't been validated (the developer
> doesn't own a Mac). macOS bug reports and PRs are welcome!

## 1. Install

### Option A: pip (recommended)

```bash
pip install agent-session-hub
```

### Option B: from source

```bash
git clone https://github.com/avidullu/agent-sessions.git
cd agent-sessions
pip install -e .
```

## 2. Install the VS Code Extension (optional)

If you use VS Code agents (Copilot Chat, DeepSeek, Continue, Cline, etc.), install the companion extension:

```bash
code --install-extension avidullu.agent-session-router
```

Or download the `.vsix` from [Releases](https://github.com/avidullu/agent-session-router/releases).

The extension auto-discovers VS Code agent sessions and exports them as Markdown files the hub can index. See the [router README](https://github.com/avidullu/agent-session-router) for details.

## 3. Configure sources

Create a private workspace, then initialize it (hub **0.3.0+**):

```bash
mkdir my-agent-archive
cd my-agent-archive
agent-archive init
```

This uses a template shipped inside the package, preserves existing configuration,
and does not collect or upload anything. Review `sources.toml` before exporting.
The default CLI sources are Codex, Claude Code, and Grok; additional sources can be
configured using the [source examples](../sources.example.toml).

For the VS Code router, run **Agent Session Router: Set Output Directory** and
select the exact archive directory printed by `init`. Then either explicitly
enable **Auto-Export — Monitor for New Sessions** or run **Export All Sessions**.
Auto-export is off by default. `agent-archive status` reads routed sessions
directly from `.router-index.jsonl`; it does not need another export first.

Already have router output? Use `agent-archive --repo-root /absolute/path/to init --archive-dir output`
(quote paths containing spaces). The output folder must be a direct child of the
workspace: router catalog paths are relative to that parent. Run subsequent hub commands from this workspace,
or use `agent-archive --repo-root /path/to/workspace status` from anywhere.
An existing source checkout can keep its configuration; `init` is not a migration.

If `init` is unrecognized, check `agent-archive --version` and upgrade after 0.3.0
is published. Version 0.2.0 requires the source-checkout setup, including copying
`sources.example.toml`; it does not support this repo-free initialization.

## 4. Discover sessions

```bash
agent-archive discover --write docs/DISCOVERY.md
```

This scans your configured sources and creates an inventory report.

## 5. Export sessions

```bash
agent-archive export --all
```

This renders your sessions as Markdown files in `archive/` and updates the catalog (`archive/index.jsonl` and `archive/INDEX.md`).

### Optional: PDF export

```bash
pip install reportlab
agent-archive export --all --pdf
```

## 6. Check status

```bash
agent-archive status
```

Shows archive freshness, new/changed files, and cross-machine convergence.

## 7. (Optional) Set up daily automation

The scheduler installers below are **source-checkout tools**, not commands included
by pip. Pip users can schedule `agent-archive --repo-root /path/to/workspace export --all`
using their OS scheduler. Keep the workspace private; no automatic Git push is needed.

From a source checkout on one primary machine, install a **local-only** daily export (no git push):

```bash
# Linux / WSL / macOS
./scripts/install-local-export-schedule.sh
# or run once:
./scripts/local-export.sh
```

```powershell
# Windows
.\scripts\install-local-export-schedule.ps1
# or run once:
.\scripts\local-export.ps1
```

Use `daily-export` (commit + push catalog) only against a **private** archive
remote. See [AUTOMATION.md](AUTOMATION.md) for both modes, privacy notes, and
Task Scheduler / cron details.

## What next?

- Read the [FAQ](FAQ.md) for common questions
- Read [CONTRIBUTING.md](../CONTRIBUTING.md) to add support for a new agent or submit fixes
- Explore the [baseline pipeline](ENGINEERING_BASELINE.md) to extract and promote rules from your sessions
- Check [COMPOSE_STACK.md](COMPOSE_STACK.md) for the full ecosystem (search, sync, live capture)

## Architecture

```
┌─────────────────────────────────┐    ┌──────────────────────────────┐
│  agent-session-router           │    │  agent-sessions (hub)         │
│  (VS Code extension)            │    │  (Python CLI)                 │
│                                 │    │                               │
│  VS Code agents → Markdown ─────┼───▶│  merge → index.jsonl          │
│  (Copilot, DeepSeek, Cline...)  │    │  CLI agents → Markdown + PDF  │
│                                 │    │  (Claude, Codex, Gemini...)   │
└─────────────────────────────────┘    │                               │
                                       │  baseline → rules → publish   │
                                       └──────────────────────────────┘
```

Both tools are **local-first** — no cloud storage, no telemetry, no network calls during export.
