# Roadmap

This archive is local-first: importers should prefer session data stored on
owned CPU/RAM and local disks, including Windows and WSL paths.

Search and live-memory features are intentionally delegated to the compose stack
instead of rebuilt here; see [COMPOSE_STACK.md](COMPOSE_STACK.md).

## Future Features

- Daily Codex automation that pulls, exports new sessions, renders PDFs, commits,
  and pushes only when the archive changes. See [AUTOMATION.md](AUTOMATION.md).
- Optional hosted/cloud session import adapters if a tool later moves chat
  history off-device. Prefer official APIs, explicit export folders, or vendor
  extension hooks over UI scraping.
- VS Code chat export inbox for any manually exported JSON or Markdown session
  files from machines that expose an official export command.
- Engineering baseline extraction that turns repeated session lessons into
  reviewable guardrails and agent-specific instruction files.
- Agent-assisted proposal generation that uses bounded, reasonable access to
  sessions, repos, PRs, issues, CI logs, and local instruction files to draft
  reviewable baseline candidates.
