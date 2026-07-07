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

- **Active tracked project:** `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` scopes
  issues #23, #25, and #26 as one sequence: schema/compiled wiki first, handoff
  mining as the first producer, replay selection/bundling/ingest after
  provenance and redaction contracts. PR #45 merged the tracker. PR #46 merged
  K1: `baseline/SCHEMA.md`, scaffold coverage, bundle packet schema references,
  and tests/docs updates. PR #47 merged K2: report-only
  `baseline handoffs audit`, writing only `baseline/handoffs/audit.md`; the K2
  audit report scanned 3,114 archive records and found 946 archive handoff
  candidates. PR #48 merged K3: shared `baseline:begin/end` marker-block
  helpers for project-page generated sections. PR #49 merged K4: read-only
  `baseline lint` skeleton for schema, marker, generated-link, stale-block,
  orphan-page, and explicit contradiction checks. PR #50 merged K5:
  proposal trace-field threading plus `archive/index.jsonl` reference
  validation for replay/handoff proposal ingest. PR #51 merged K6: persistent
  `baseline/handoffs/index.jsonl`, marker-owned `handoffs.index` project-page
  feeds for configured/existing pages, and small #49/#50 review follow-ups.
  K7 is active on branch `codex/handoff-proposal-generation` in
  `C:\Users\avidu\Projects\Agent Sessions - handoff-proposals`: generated
  handoff-derived proposal JSON under `baseline/proposals/`, structured trace
  validation through `baseline ingest --dry-run`, and the #51 review follow-up
  that keeps project-page feed dates stable when generated content is unchanged.
  Related issue #19 is folded in as lightweight provenance substrate; #32
  remains separate backfill/regenerate work, including any future handoff-index
  prune semantics.
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
- `baseline/SCHEMA.md`
- `baseline/handoffs/audit.md`
- `baseline/handoffs/index.jsonl`
- `baseline/proposals/handoff.*.handoff-signals.json`
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
- Handoff split decision (2026-07-07): K2 audit is report-only and may write
  `baseline/handoffs/audit.md`; K6 owns persistent handoff index writes and
  downstream project-page/proposal feeds.
- K1 review follow-ups handled in K2 branch (2026-07-07): golden drift guard
  for `baseline/SCHEMA.md` vs `baseline_schema()`, explicit absent-schema
  branch coverage, and clarified calibration TOML artifacts in the schema table.
- K3 project-page upsert decision (2026-07-07): project-page producers reuse
  the shipped `baseline:begin/end` marker grammar via
  `render_project_page_block()` and `upsert_project_page_content()`; no second
  marker family or free-form page rewrite path.
- K3 review follow-ups carried into PR #49 (2026-07-07): deduped project-page
  placeholder text between `baseline_settings` and `baseline_promote`;
  documented/tested exact-line placeholder matching as intentionally safer; and
  added a golden byte-output test for empty-file `upsert_promoted_content()`.
- K4 lint severity decision (2026-07-07): malformed markers and broken generated
  links are errors; orphan pages, stale blocks, and explicit contradiction
  markers start as warnings until downstream producers provide richer source
  records.
- K4 review follow-ups (2026-07-07): K6 folds in invalid generated-date lint
  warnings instead of exceptions; K12 should still map rule ids to gate ids
  explicitly; duplicate baseline markdown reads are acceptable for now but can
  be optimized if the tree grows.
- K5 trace validation decision (2026-07-07): human proposals keep optional
  free-text evidence; `source_kind` of `replay`, `handoff`, or `repo-handoff`
  requires structured trace and resolvable `markdown_path`/`session_id`
  references before candidate sidecars are written.
- K6 handoff index decision (2026-07-07): persist every discovered handoff
  candidate in `baseline/handoffs/index.jsonl`, but only write project-page
  feed blocks to configured or existing pages. Configured pilot aliases collapse
  multiple raw paths into the canonical slug; digest disambiguators are reserved
  for unknown slug collisions.
- K7 handoff proposal decision (2026-07-07): generated handoff proposals are
  deterministic review inputs for configured/existing projects only. They carry
  `generated_by = "baseline handoffs proposals"` and `source_kind =
  "repo-handoff"`, refuse to overwrite hand-written proposals, and must pass
  `baseline ingest --dry-run` before review.
- K6 review follow-up folded into K7 (2026-07-07): `handoffs.index` project-page
  feeds preserve the existing `generated_at` value when the generated feed
  content is otherwise unchanged, avoiding date-only churn on periodic runs.
- K5 review follow-up folded into K6 (2026-07-07): `normalized_markdown_path()`
  now removes only explicit `./` or leading `/` path prefixes rather than using
  `lstrip("./")`.
