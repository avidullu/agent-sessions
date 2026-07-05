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
