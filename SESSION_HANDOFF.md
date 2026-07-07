# Session Handoff

Updated: 2026-07-07 20:43 IST

## You Are Here

`C:\Users\avidu\Projects\Agent Sessions` is a private GitHub-backed archive for
agent coding sessions. The exporter is the `agent_sessions` package, with
TOML-backed source definitions and per-agent extractors for Codex, Claude, Grok,
DeepSeek, Gemini Antigravity, and known VS Code extension locations.

The active tracked project is `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md`, covering
issues #23, #25, and #26 as one safety-first sequence:

1. schema and marker-owned knowledge pages;
2. deterministic handoff mining as the first producer;
3. replay selection, redaction, bundling, and ingest after provenance gates.

Today landed a long run of small PRs:

- #45 K0: design tracker for #23/#25/#26.
- #46 K1: `baseline/SCHEMA.md` and scaffold/schema wiring.
- #47 K2: report-only `baseline handoffs audit`.
- #48 K3: shared project-page marker-block upsert helpers.
- #49 K4: read-only `baseline lint` skeleton.
- #50 K5: proposal trace propagation and archive-reference validation.
- #51 K6: persistent `baseline/handoffs/index.jsonl` plus `handoffs.index`
  project-page feeds for configured or existing project pages only.
- #52 K7: `baseline handoffs proposals` deterministic proposal JSON generation
  with a hand-written-proposal overwrite guard and the #51 stable generated-date
  follow-up.
- #53 K8: `baseline replay select` deterministic, excerpt-free replay manifest
  excluding coding sessions (D5); idempotent for gate R2-dedup.
- #54 K9: `baseline replay redact` deterministic fail-closed secret scanner and
  valueless redaction report; egress remains gitignored.
- #55 K10: `baseline replay bundle` writes gitignored redacted packets
  (task + deliverable + rubric + report) only for sessions that pass the K9 gate.

PR #56 is open for K11:

- Branch: `claude/replay-ingest`
- `baseline replay ingest --result <path>` validates an external replay result
  (its `replay_of`/trace references must resolve against `archive/index.jsonl`),
  appends every result to the append-only `baseline/replay/ledger.jsonl`, and —
  for `recommended_action == "proposal"` — emits a `replay.*` proposal that
  passes the K5 `validate_proposal` gate and flows through `baseline ingest`.
  Unresolvable results are rejected (non-zero) and recorded in the ledger.
- No dogfood artifacts committed: a fabricated replay result would inject a
  synthetic candidate into the real baseline, so only tests exercise it.

## Next Steps / Open Threads

1. K12 is the last slice: wire the W/H/R efficacy gates into `baseline eval`
   (schema-lint clean, handoff precision/freshness, replay R1-R5, no
   auto-promotion) and flip the remaining tracker rows to `Done`, then mark the
   project `DONE`/archived.
2. Merge gate for every slice: `git diff --check`, `ruff`, `mypy`, full pytest
   with coverage, plus `baseline lint --dry-run` when generated artifacts change.

Known open boundaries:

- #32 remains the right boundary for archive backfill/regenerate work and any
  future `baseline/handoffs/index.jsonl --prune` semantics.
- The two `baseline lint` orphan warnings for `baseline/projects/agent-sessions`
  and `baseline/projects/avidullu` are known warnings, not PR blockers.
- Replay execution stays out-of-band in v1. This repo selects and validates
  packets/results; it does not autonomously run alternate agents.

## Ramp-Up Kit

- `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md`
- `baseline/SCHEMA.md`
- `docs/ENGINEERING_BASELINE.md`
- `docs/TEST_PLAN.md`
- `docs/BASELINE_LOOP_CLOSURE.md`
- `docs/CALIBRATION_EFFICACY.md`
- `docs/COMPOSE_STACK.md`
- `baseline/handoffs/audit.md`
- `baseline/handoffs/index.jsonl`
- `baseline/proposals/handoff.*.handoff-signals.json`
- `agent_sessions/baseline_handoffs.py`
- `agent_sessions/baseline_ingest.py`
- `agent_sessions/baseline_lint.py`
- `agent_sessions/baseline_promote.py`
- `agent_sessions/cli.py`
- `tests/test_baseline_handoffs.py`
- `tests/test_baseline_ingest.py`
- `tests/test_baseline_lint.py`
- `tests/test_cli.py`

## Key Decisions

- Private GitHub repo: `https://github.com/avidullu/agent-sessions`
- Raw source backups remain ignored by Git by default.
- Exported Markdown/PDF files under `archive/` are committed and pushed.
- Preserve transcript text as-is, even if generated Markdown contains trailing
  whitespace from original session content.
- Default source paths use template variables instead of user-specific hardcoded
  Windows/WSL paths.
- Knowledge/replay sequencing: schema and deterministic marker-block page
  writes come before handoff mining or replay egress.
- Handoff split: K2 audit is report-only; K6 owns persistent handoff index and
  project-page feeds; K7 owns proposal generation.
- Project-page producers reuse the shipped `baseline:begin/end` marker grammar;
  there is no second marker family and no free-form page rewrite path.
- Trace validation: human proposals may keep free-text evidence, but
  `source_kind` of `replay`, `handoff`, or `repo-handoff` requires structured
  trace and resolvable archive references before candidate sidecars are written.
- K6 handoff index: persist every discovered handoff candidate in
  `baseline/handoffs/index.jsonl`, but write project-page feeds only for
  configured or already-existing pages.
- K7 generated proposals: deterministic review inputs only, scoped to
  configured/existing projects, with `generated_by = "baseline handoffs
  proposals"` and `source_kind = "repo-handoff"`. They must pass
  `baseline ingest --dry-run` and are never auto-promoted.
- K7 stable-date follow-up: `handoffs.index` project-page feeds preserve the
  existing `generated_at` value when generated content is unchanged.
