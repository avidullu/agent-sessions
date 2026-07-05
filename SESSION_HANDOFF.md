# Session Handoff

## You Are Here

`C:\Users\avidu\Projects\Agent Sessions` is a private GitHub-backed archive for
agent coding sessions. The exporter is organized as the `agent_sessions` package,
with TOML-backed source definitions and per-agent extractors registered by
source kind. It exports local session data to Markdown and PDF from Codex,
Claude, Grok, DeepSeek, Gemini Antigravity, and known VS Code extension
locations where transcript-like files are discoverable.

## Next Steps / Open Threads

- Add a daily Codex automation for pull/export/PDF/commit/push once the desired
  schedule is chosen.
- Keep hosted/cloud session imports as optional future work only; the current
  assumption is local-owned compute and storage.
- Improve VS Code Copilot/ZAI importers if reliable transcript files or official
  export locations are identified.
- Build the engineering-baseline extraction flow described in
  `docs/ENGINEERING_BASELINE.md`.
- Iterate on the planning details in `docs/BASELINE_PLANNING.md`, especially
  pilot repo config, AI-assisted proposal generation, and approval policy.
- First implementation slice adds baseline scaffold files and
  `python .\tools\agent_archive.py baseline suggest` for deterministic
  candidate/metacognition reports.
- Next slice adds structured prediction sidecars, a metacognition ledger, and
  `baseline calibrate` summaries.
- AI proposal adapter slice adds `baseline bundle` for local evidence packets
  that authorized agents can use to draft structured baseline proposals.

## Ramp-Up Kit

- `README.md`
- `docs/DISCOVERY.md`
- `docs/ROADMAP.md`
- `docs/ENGINEERING_BASELINE.md`
- `docs/BASELINE_PLANNING.md`
- `tools/agent_archive.py`
- `agent_sessions/`
- `baseline/`
- `config/baseline.toml`
- `sources.example.toml`
- `config/default_sources.toml`

## Key Decisions

- Private GitHub repo: `https://github.com/avidullu/agent-sessions`
- Raw source backups remain ignored by Git by default.
- Exported Markdown/PDF files under `archive/` are committed and pushed.
- Preserve transcript text as-is, even if generated Markdown contains trailing
  whitespace from original session content.
- Default source paths use template variables instead of user-specific hardcoded
  Windows/WSL paths.
