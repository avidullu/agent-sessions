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
- #56 K11: `baseline replay ingest` validates external replay results into
  `replay.*` proposals (K5-gated) + an append-only `baseline/replay/ledger.jsonl`.
- #57 K12: efficacy gates (W1/W2, H1/H2, R1-R5, `G-no-autopromote`) wired into
  `baseline eval` with a `gated` status; real-repo run 14 pass / 0 fail / 2 gated.

## Status: knowledge + replay tracker COMPLETE (K0-K12)

`docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` is `DONE` — every K row landed via PRs
#45-#57. The knowledge layer (SCHEMA, marker upserts, lint), handoff mining
(audit -> index -> project feeds -> proposals), and the replay loop
(select -> redact -> bundle -> ingest) are all implemented, deterministic, and
human-gated. `baseline eval` now reports the E + W/H/R gate battery.

The only pending signal is empirical, not code: `R3-signal`/`R4-value` stay
`gated` until a real out-of-band replay result is ingested — replay execution is
out-of-band by design (D4). The first real replay run will flip those.

The 2026-07-08 audit is recorded in `docs/WORK_AUDIT_2026-07-08.md`; it marks
the original baseline loop closure as historical/done and captures the current
follow-up set.

## Next Steps / Open Threads

- Optional: archive the tracker doc per its lifecycle once satisfied; run a real
  replay (hand a `baseline replay bundle` packet to a cross-lineage agent, then
  `baseline replay ingest` the result) to exercise R3/R4 with live data.
- Follow-up issues: #60 collects replay/knowledge v1 polish (richer replay
  slugs, clean bundle reruns, project-scoped replay proposals, stronger
  precision/dedup gates); #59 tracks entropy/vendor/JWT redaction hardening; #32
  remains archive backfill/regenerate; #19 remains broader trace/explain work.

Known open boundaries:

- #32 remains the right boundary for archive backfill/regenerate work and any
  future `baseline/handoffs/index.jsonl --prune` semantics.
- The two `baseline lint` orphan warnings for `baseline/projects/agent-sessions`
  and `baseline/projects/avidullu` are known warnings, not PR blockers.
- Replay execution stays out-of-band in v1. This repo selects and validates
  packets/results; it does not autonomously run alternate agents.

## Ramp-Up Kit

- `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md`
- `docs/WORK_AUDIT_2026-07-08.md`
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
