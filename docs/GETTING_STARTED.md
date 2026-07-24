# Getting Started — Agent Sessions

A 5-minute guide to archiving your AI coding sessions.

## Prerequisites

- **Python 3.11+** — check with `python3 --version`
- **Git** — for cloning and versioning your archive
- One or more AI coding agents (Claude Code, Codex CLI, Gemini CLI, Grok, DeepSeek, or VS Code Copilot Chat via the router extension)

> **Platform note:** This tool has been manually tested on **Windows, WSL, and Ubuntu**.
> macOS should work through the same code paths but hasn't been validated (the developer
> doesn't own a Mac). macOS bug reports and PRs are welcome!

## 1. Install

### Option A: pip (recommended)

```bash
pip install agent-sessions
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
code --install-extension agent-session-router
```

Or download the `.vsix` from [Releases](https://github.com/avidullu/agent-session-router/releases).

The extension auto-discovers VS Code agent sessions and exports them as Markdown files the hub can index. See the [router README](https://github.com/avidullu/agent-session-router) for details.

## 3. Configure sources

Copy the example config and edit it for your machine:

```bash
cp sources.example.toml sources.toml
```

Edit `sources.toml` to point at your agent session directories. See `sources.example.toml` for platform-specific examples (Windows, macOS, Linux, WSL).

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

See [AUTOMATION.md](AUTOMATION.md) for cron/scheduled-task scripts that auto-export daily.

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
