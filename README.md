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
python .\tools\agent_archive.py discover --write docs\DISCOVERY.md
python .\tools\agent_archive.py export --all
```

Optional PDF output:

```powershell
python -m pip install reportlab
python .\tools\agent_archive.py export --all --pdf
```

Optional raw backups:

```powershell
python .\tools\agent_archive.py export --all --copy-raw
```

Raw files land under `raw/`, which is ignored by Git unless you intentionally
force-add it.

## Adding Agents

1. Add a source entry in `config/default_sources.toml` or local `sources.toml`.
2. Add an extractor module under `agent_sessions/sources/`.
3. Register it with `@register("<kind>")`.
4. Run a dry export with `--source <kind> --limit 1 --dry-run`.

## Engineering Baseline

Create or refresh the baseline scaffold:

```powershell
python .\tools\agent_archive.py baseline scaffold
```

Generate reviewable candidate predictions from the archive:

```powershell
python .\tools\agent_archive.py baseline suggest
```

Candidate reports are suggestions with provenance and calibration hooks. Copy
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

## Other Machines

Clone this private repo on another machine, run the same discovery/export
commands there, commit the new `archive/` Markdown/PDF files, and push.

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
