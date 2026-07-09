# Feedback Incorporation Tracker

> **Status:** `DONE / archived` - July 2026 external feedback review execution tracker.
> **Owner:** `avidullu`. **Created:** `2026-07-09`. **Archived:** `2026-07-09`.
> **Scope:** `agent-sessions` hub plus `agent-session-router` feeder extension.

## 0. Outcome

The feedback workstream is complete. The useful feedback was incorporated in
small PRs across the hub and router repos, with one remaining broad performance
idea intentionally left in backlog until profiling shows it is needed.

Primary outcomes:

- Archive freshness, user insights, and the project tracker landed in hub PR #68.
- Gemini Antigravity identity is stable in router PR #18.
- Rendered archive Markdown/PDF bodies are local-only by default in hub PR #69.
- Router sidecar identity now matches the hub catalog identity in router PR #19.
- Router large-file robustness, export accounting, and plan freshness landed in
  router PRs #20, #21, and #22.
- Tail-hash reuse hardening landed in router PR #23 and hub PR #70.

## 1. Decisions

| # | Decision | Final disposition |
| --- | --- | --- |
| D1 | Treat archive freshness as P0. | Done in hub PR #68. |
| D2 | Treat `archive/.router/` as local diagnostics, not durable archive state. | Done in hub PR #68 / #69. |
| D3 | Fix router Gemini `metadata.session_id` before deeper parser refactors. | Done in router PR #18. |
| D4 | Add tail-hash/idempotency hardening after P0/P1 identity work. | Done in router PR #23 and hub PR #70. |
| D5 | Defer broad generator rewrites until profiling or larger scale justifies them. | Evaluated and left in backlog. Source extractors already stream JSONL, and baseline commands currently benefit from list-based summaries. |
| D6 | Keep rendered archive Markdown/PDF bodies local-only by default; track catalog metadata in Git. | Done in hub PR #69. |

## 2. Deliverables

| ID | Priority | Repo | Deliverable | Status | PR |
| --- | --- | --- | --- | --- | --- |
| F0 | P0 | `agent-sessions` | Check in tracker, refresh archive, ignore local router diagnostics, regenerate insights. | Done | #68 merged |
| F1 | P0 | `agent-session-router` | Populate Gemini Antigravity `metadata.session_id` from the discovered session path. | Done | #18 merged |
| F2 | P0 | `agent-sessions` | Make rendered archive Markdown/PDF files local-only by default; keep `archive/index.jsonl` and `archive/INDEX.md` as shared metadata. | Done | #69 merged |
| F3 | P0 | `agent-session-router` | Align router sidecar identity with hub catalog identity (`session_id` + `sha256`) and document local-only Markdown impact. | Done | #19 merged |
| F4 | P1 | `agent-session-router` | Stream Gemini JSONL parsing and file hashing instead of full-file `readFileSync`. | Done | #20 merged |
| F5 | P1 | `agent-session-router` | Split skipped vs failed export accounting. | Done | #21 merged |
| F6 | P1 | `agent-session-router` | Refresh `PLAN.md` to match shipped support and current next steps. | Done | #22 merged |
| F7 | P2 | both | Add tail-hash identity hardening for append-only logs. | Done | Router #23 and hub #70 merged |
| F8 | P2 | `agent-sessions` | Evaluate targeted generator APIs for baseline/index scans. | Backlog by design | No PR |

## 3. F8 Evaluation

The "make JSONL readers/generator APIs broader" feedback was reviewed after the
P0/P1/P2 fixes landed. No code change was made because:

- source extractors already use streaming `jsonl_objects`;
- archive hashing and router hashing now stream/chunk large files;
- baseline/index consumers intentionally materialize records for summary counts,
  source/kind counters, project-hit calculations, and report rendering;
- the current archive size is handled within the existing coverage/performance
  envelope;
- a generator refactor would touch many baseline contracts without evidence of
  memory or latency pressure.

Backlog trigger: revisit targeted generator APIs if archive/index scans show
measurable memory pressure, slow baseline runs, or a new command needs true
streaming semantics.

## 4. Verification Summary

Hub PR #70 local verification:

- `python -m pytest tests/test_archive.py tests/test_archive_status.py`
- `python -m pytest --cov=agent_sessions --cov-report=term-missing`
  - `598 passed`
  - total coverage `96.84%`
- `ruff check .`
- `mypy agent_sessions`
- `git diff --check`

Router PRs #20-#23 local verification used:

- `npm test`
- `npm run lint:check`
- targeted Prettier checks
- `git diff --check`

Substantive GitHub CI passed for every merged PR. The router repo's PR labeler
workflow repeatedly failed independently of product code and was treated as
non-blocking.

## 5. Final Repo Heads

After the workstream:

| Repo | Base branch | Final merged PRs in this workstream |
| --- | --- | --- |
| `agent-sessions` | `main` | #68, #69, #70, plus this archive PR |
| `agent-session-router` | `master` | #18, #19, #20, #21, #22, #23 |

## 6. Archived Notes

The tracker has moved from `docs/FEEDBACK_INCORPORATION_TRACKER_2026-07-09.md`
to `docs/archives/FEEDBACK_INCORPORATION_TRACKER_2026-07-09.md`. It is no
longer an active planning artifact.
