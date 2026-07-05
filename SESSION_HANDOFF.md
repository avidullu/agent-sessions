# Session Handoff

## You Are Here

`C:\Users\avidu\Projects\Agent Sessions` is a private GitHub-backed archive for
agent coding sessions. It currently exports local session data to Markdown and
PDF from Codex, Claude, Grok, DeepSeek, Gemini Antigravity, and known VS Code
extension locations where transcript-like files are discoverable.

## Next Steps / Open Threads

- Add a daily Codex automation for pull/export/PDF/commit/push once the desired
  schedule is chosen.
- Keep hosted/cloud session imports as optional future work only; the current
  assumption is local-owned compute and storage.
- Improve VS Code Copilot/ZAI importers if reliable transcript files or official
  export locations are identified.

## Ramp-Up Kit

- `README.md`
- `docs/DISCOVERY.md`
- `docs/ROADMAP.md`
- `tools/agent_archive.py`
- `sources.example.toml`

## Key Decisions

- Private GitHub repo: `https://github.com/avidullu/agent-sessions`
- Raw source backups remain ignored by Git by default.
- Exported Markdown/PDF files under `archive/` are committed and pushed.
- Preserve transcript text as-is, even if generated Markdown contains trailing
  whitespace from original session content.
