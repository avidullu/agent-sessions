# Frequently Asked Questions

## What's the difference between agent-sessions and agent-session-router?

**agent-sessions** (this repo) is the Python hub — it discovers and exports sessions from CLI-based AI coding agents (Claude Code, Codex CLI, Gemini CLI, Grok, DeepSeek). It also owns the archive format, the shared catalog, and the baseline pipeline.

**agent-session-router** is a VS Code extension — it discovers and exports sessions from VS Code-based agents (Copilot Chat, Continue, Cline, Cody, Aider). It writes Markdown in the hub's format so the hub can index them.

Together they cover every AI coding agent you might use.

## Does this upload my sessions anywhere?

**No.** All processing is local. Sessions are read from your machine's agent stores, parsed, and written as local Markdown files. Nothing is sent over the network. There is no telemetry, no cloud storage, no API calls.

## Which AI coding agents are supported?

| Agent | Via |
|-------|-----|
| Claude Code | Direct Python importer |
| Codex CLI | Direct Python importer |
| Gemini Antigravity | Direct Python importer |
| Grok | Direct Python importer |
| DeepSeek V4 (VS Code) | Direct Python importer |
| GitHub Copilot Chat | Router extension |
| Continue.dev | Router extension |
| Cline | Router extension |
| Cody (Sourcegraph) | Router extension |
| Aider | Router extension |
| Tabby, Codeium, Amazon Q | Router extension (generic fallback) |

## What platforms are supported?

The tools have been **manually tested on Windows, WSL, and Ubuntu**. macOS should work through the same code paths but hasn't been validated — the developer (humorously) doesn't own a Mac device. If you hit macOS-specific issues, please file a bug. PRs welcome!

## How do I install?

**Hub** (Python CLI):
```bash
pip install agent-session-hub
```

**Router** (VS Code extension):
```bash
code --install-extension agent-session-router
```

Or download the `.vsix` from [Releases](https://github.com/avidullu/agent-session-router/releases).

See [Getting Started](GETTING_STARTED.md) for detailed setup.

## What platforms are supported?

The tools have been **manually tested on Windows, WSL, and Ubuntu**. macOS should work through the same code paths but hasn't been validated — the developer (humorously) doesn't own a Mac device. If you hit macOS-specific issues, please file a bug. PRs welcome!

## Where are my exported sessions saved?

To the `archive/` directory inside the agent-sessions repo (configurable via `sources.toml`). Files are organized by source: `archive/claude-windows/`, `archive/codex-macos/`, etc.

By default, Git tracks only the catalog metadata (`archive/index.jsonl` and `archive/INDEX.md`). Rendered transcript bodies are local-only files — they stay on your machine unless you explicitly configure Git tracking.

## How do I add support for a new AI agent?

**Router** (VS Code agents): Drop a discoverer + extractor pair into `src/discoverers/` and `src/extractors/`. See the [router README](https://github.com/avidullu/agent-session-router#adding-custom-agents) for the recipe.

**Hub** (CLI agents): Add a source module in `agent_sessions/sources/` and a config entry in `sources.toml`. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Can I use the router without the hub?

Yes. The router writes standalone Markdown files — you can read them directly. The hub adds indexing, search integration (via `cass`), and the baseline pipeline — entirely optional.

## How do I update?

**Hub:**
```bash
pip install --upgrade agent-sessions
```

**Router:**
```bash
git pull origin master && npm ci && npm run compile
npx @vscode/vsce package -o agent-session-router.vsix
code --install-extension agent-session-router.vsix --force
```

Or wait for Marketplace auto-updates once published.

## The router watcher isn't working. What do I check?

1. Open the Output panel (`View` → `Output` → "Agent Session Router") for `[watcher]` events
2. Ensure `agentSessionRouter.watch.enabled` is `true` in VS Code settings
3. The watcher only exports sessions modified **after** it starts
4. Run **Export Diagnostic Bundle** to collect logs for debugging

## What's redacted from exports and why?

The hub applies **redaction-v1** to all exported text:
- **High-confidence secrets**: API tokens, private keys, password-like patterns — **blocked** (session is skipped)
- **User paths**: Home directory paths (`/home/<user>/...`, `C:\Users\<user>\...`) — **placeholdered** (replaced with `<path-N>`)

Redaction is best-effort — always review exported transcripts before sharing. See [ENGINEERING_BASELINE.md](ENGINEERING_BASELINE.md) for details.

## There are a few different names — which is which?

The project spans a couple of registries, so it wears a few names:

| Where | Name | How you use it |
|-------|------|----------------|
| GitHub repo / project | `agent-sessions` | browse the source |
| PyPI package (the hub) | `agent-session-hub` | `pip install agent-session-hub` |
| Command it installs | `agent-archive` | `agent-archive export --all` |
| Python import | `agent_sessions` | `import agent_sessions` |
| VS Code extension | `avidullu.agent-session-router` | `code --install-extension avidullu.agent-session-router` |

The PyPI distribution is `agent-session-hub` (not `agent-sessions`) because the plain name was already taken on PyPI by an unrelated package. The command stays `agent-archive` and the import stays `agent_sessions`, so nothing about day-to-day use changes.

## How do I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md). The short version: fork, branch, run `./scripts/local_ci.sh`, open a PR. One change per PR. All gates must be green.
