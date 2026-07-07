# Session Handoff

## You Are Here

`C:\Users\avidu\Projects\Agent Sessions` is a private GitHub-backed archive for
agent coding sessions. The exporter is organized as the `agent_sessions` package,
with TOML-backed source definitions and per-agent extractors registered by
source kind. It exports local session data to Markdown and PDF from Codex,
Claude, Grok, DeepSeek, Gemini Antigravity, and known VS Code extension
locations where transcript-like files are discoverable.

The archive now has merge-aware indexing, `python .\tools\agent_archive.py
status`, and docs for multi-machine archive convergence. Local status on
2026-07-06 showed 3,114 indexed records, 0 new visible files, 2 changed visible
files, and two inferred origin environments: `windows-user:C:/Users/avidu` and
`wsl-user:Ubuntu:/home/avidullu`.

## Next Steps / Open Threads

- **Design review:** `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` scopes issues #23,
  #25, and #26 as one sequence: schema/compiled wiki first, handoff mining as the
  first producer, replay selection/bundling/ingest after provenance and redaction
  contracts. Draft PR #45 is open with review feedback addressed on-branch:
  K3 maps to loop-closure P6, K8 depends on P10/P11 redaction/dedup, and K2
  reuses the shipped marker/upsert machinery from TD4 #31. Related issue #19 is
  folded in as lightweight provenance substrate; #32 remains separate
  backfill/regenerate work.
- **Completed tracked project:** `docs/FIRST_USER_SETUP_TRACKER.md` (#42 + #18
  setup UX). MVP completed by PRs #43 and #44; optional future work is the P7
  `doctor`/`setup` command. Issue #32 remains separate backfill/regenerate work
  except for boundary notes.
- **Active tracked project:** `docs/BASELINE_LOOP_CLOSURE.md` (§7 closure tracker).
- **Completed tracked project:** tech-debt remediation (TD1-TD15, PRs #28-#40)
  is DONE and archived at `docs/archives/TECH_DEBT_PLAN.md`. Related follow-up:
  issue #32 (index backfill + `regenerate`).
- **Efficacy gates:** `docs/CALIBRATION_EFFICACY.md` and `baseline/calibration/efficacy.toml`.
- **Merged:** PRs #13-#17 cover baseline promote, publish, calibration/eval,
  structured proposal ingest, and multi-machine archive status/merge behavior.
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
- Compose-stack scope is now explicit: this repo owns archive and baseline;
  search/live memory/Claude-specific UX are delegated externally.
- Daily export automation lives in `scripts/daily-export.*` and
  `docs/AUTOMATION.md`.

## Ramp-Up Kit

- `README.md`
- `docs/DISCOVERY.md`
- `docs/FIRST_USER_SETUP_TRACKER.md`
- `docs/NEW_MACHINE_SETUP.md`
- `docs/ROADMAP.md`
- `docs/ENGINEERING_BASELINE.md`
- `docs/BASELINE_PLANNING.md`
- `docs/README.md`
- `docs/BASELINE_LOOP_CLOSURE.md`
- `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md`
- `docs/archives/TECH_DEBT_PLAN.md`
- `docs/CALIBRATION_EFFICACY.md`
- `docs/PROJECT_DOC_TEMPLATE.md`
- `docs/COMPOSE_STACK.md`
- `docs/AUTOMATION.md`
- `docs/MULTI_MACHINE.md`
- `baseline/calibration/efficacy.toml`
- `tools/agent_archive.py`
- `agent_sessions/`
- `baseline/`
- `scripts/daily-export.ps1`
- `scripts/daily-export.sh`
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
- Knowledge/replay sequencing decision (2026-07-07): land `baseline/SCHEMA.md`
  and deterministic project-page marker blocks before handoff mining or replay;
  replay execution stays out-of-band and excludes coding sessions in v1.
