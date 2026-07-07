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

PR #52 is open for K7:

- URL: https://github.com/avidullu/agent-sessions/pull/52
- Branch: `codex/handoff-proposal-generation`
- Worktree: `C:\Users\avidu\Projects\Agent Sessions - handoff-proposals`
- Head: `e6dd3a0 Record K7 PR number`
- State at 2026-07-07 20:43 IST: open, CI green, no review comments/reviews yet.

K7 adds `baseline handoffs proposals`, generates deterministic proposal JSON for
configured/existing projects, refuses to overwrite hand-written proposal files,
and validates generated handoff proposals through `baseline ingest --dry-run`.
It also folds in the #51 review follow-up that `handoffs.index` blocks should
preserve their existing `generated_at` date when the generated feed content is
unchanged, avoiding date-only churn on periodic runs.

Verification already run for PR #52:

- `git diff --check`
- `python -m ruff check .`
- `python -m mypy agent_sessions tools`
- `python -c "from agent_sessions.cli import main; raise SystemExit(main(['baseline','lint','--dry-run']))"`
  - 0 errors, 2 known `W2-orphan` warnings for `agent-sessions` and `avidullu`
- `python -c "from agent_sessions.cli import main; raise SystemExit(main(['baseline','ingest','--dry-run']))"`
  - 5 accepted, 0 rejected
- `python -m pytest --cov=agent_sessions --cov-report=term-missing`
  - 495 passed, 97.05% coverage

The temporary 10-minute PR polling heartbeat from this session was deleted when
this handoff was refreshed, because remaining work will resume in a new session.

## Next Steps / Open Threads

1. Start the new session by following the repo freshness rule: `git pull
   --ff-only` before reading the relevant checkout. If the primary checkout has
   local `SESSION_HANDOFF.md` edits that block fast-forward, do not clobber
   them; use the K7 worktree or a fresh worktree.
2. Check PR #52 first:
   - `gh pr view 52 --repo avidullu/agent-sessions --json state,reviewDecision,statusCheckRollup,latestReviews,comments`
   - use the `github:gh-address-comments` workflow if review comments exist.
3. If #52 gets LGTM/merge-ready and CI is green, run the merge gate locally
   before merging: `git diff --check`, `ruff`, `mypy`, full pytest with
   coverage, plus baseline lint/ingest dry-runs when relevant. Then merge #52.
4. After #52 merges, update `docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` K7 to
   `Done`, refresh this handoff, and start the next tracker item in order.
5. Next implementation item is K8: `baseline replay select` deterministic
   manifests excluding coding sessions. Start it from `origin/main` in a fresh
   `codex/...` branch. K8 should not create replay bundles or egress excerpts;
   K9 owns redaction and K10 owns bundle writing.

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
