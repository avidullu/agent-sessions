# Feedback Incorporation Tracker

> **Status:** `IN PROGRESS` - execution tracker for July 2026 external feedback review. **Owner:** `avidullu`. **Created:** `2026-07-09`. **Last updated:** `2026-07-09`
> **Lifecycle:** `DRAFT -> IN PROGRESS -> DONE -> archived`
> **Tracking anchors:** Section 7 is the source of truth; indexed in `docs/README.md`.
> **Scope:** `agent-sessions` hub plus `agent-session-router` feeder extension.
> **Honesty note:** this tracker records only verified local state from the synced remote heads. Backlog rows are intentionally not promises to ship immediately.

---

## 0. TL;DR

Two external feedback artifacts were reviewed:

- `agent-sessions-feedback.pdf`
- `gemini-review.md`

The useful feedback clusters into archive freshness, Gemini/router identity and
large-file robustness, project planning freshness, and lower-priority
idempotency/performance hardening. Some feedback was already stale by the time
of review: Gemini support and aggregator-agent router support had already
landed on `origin/master` of `agent-session-router`.

## 1. Current Verified State

As of 2026-07-09 after fetching and fast-forwarding:

| Repo | Branch | Remote head | Local state |
| --- | --- | --- | --- |
| `agent-sessions` | `main` | `edb8d24` | P0 archive sync branch carries generated archive backlog plus this tracker |
| `agent-session-router` | `master` | `5ca717e` | clean before P0 Gemini identity branch |

Archive freshness from `python .\tools\agent_archive.py status --json` after
the P0 export/index-identity fix:

| Metric | Value |
| --- | ---: |
| Indexed records | `5231` |
| Visible configured files | `5215` |
| New visible files | `0` |
| Changed visible files | `2` |
| Indexed records not visible from this machine | `16` |

## 2. Decisions Locked

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | Treat archive freshness as P0, but keep it in a dedicated archive-sync PR. | Baseline/replay quality depends on recent sessions, and the diff is intentionally large/generated. |
| D2 | Treat `archive/.router/` as local diagnostics, not durable archive state. | The durable feeder sidecar is `archive/.router-index.jsonl`; diagnostics are local and can be large. |
| D3 | Fix router Gemini `metadata.session_id` before deeper parser refactors. | Session identity drives cross-machine merge/dedupe in both router and hub index logic. |
| D4 | Defer tail-hash/idempotency changes until after P0 freshness and identity work. | Current size+mtime behavior is documented and tested; useful hardening, not the first blocker. |
| D5 | Defer broad generator rewrites until profiling or larger scale justifies them. | Source extractors already stream JSONL; baseline/index list materialization is acceptable at current size. |

## 3. Pushback / Stale Feedback

| Feedback | Disposition | Reason |
| --- | --- | --- |
| "Untracked Gemini files should be committed immediately." | Stale; resolved by syncing router to `origin/master`. | Gemini support is already merged upstream; local untracked copies were stale branch residue. |
| "Prioritize Continue.dev and Cline next." | Stale for implementation, still useful for docs cleanup. | README shows Continue/Cline/Cody/Aider/Tabby/Codeium/Amazon Q support already merged; `PLAN.md` remains stale. |
| "Make `read_jsonl_dicts` a generator everywhere." | Backlog. | The repo already has `jsonl_objects` for streaming source extractors; baseline commands currently benefit from list-based summaries. |

## 4. P0 PR Boundaries

1. `agent-sessions`: archive freshness sync plus tracker and diagnostics ignore.
2. `agent-session-router`: Gemini Antigravity extractor must set stable
   `metadata.session_id`, with tests proving router index identity uses it.

## 5. Backlog Boundaries

Backlog rows are deliberately split from P0:

- stream router JSONL extraction and hashing for large files;
- fix router skipped/failed accounting;
- refresh router `PLAN.md`;
- add tail-hash identity hardening to hub/router reuse checks;
- consider targeted generator APIs for baseline scans only after profiling.

## 6. Verification Plan

| Repo | Required check before PR |
| --- | --- |
| `agent-sessions` | `python -m pytest --cov=agent_sessions --cov-report=term-missing`; `python .\tools\agent_archive.py status --json` |
| `agent-session-router` | `npm test` |

## 7. Deliverables & Progress Tracker

Legend: `Todo`, `In progress`, `Done`, `Backlog`. One small PR per row.

| ID | Priority | Repo | Deliverable | Status | PR |
| --- | --- | --- | --- | --- | --- |
| F0 | P0 | `agent-sessions` | Check in this tracker and archive freshness sync; ignore local router diagnostics. | In progress | this PR |
| F1 | P0 | `agent-session-router` | Populate Gemini Antigravity `metadata.session_id` from the discovered session path and cover index identity. | Todo | separate PR |
| F2 | P1 | `agent-session-router` | Stream Gemini JSONL parsing and file hashing instead of full-file `readFileSync`. | Backlog | - |
| F3 | P1 | `agent-session-router` | Split skipped vs failed export accounting. | Backlog | - |
| F4 | P1 | `agent-session-router` | Refresh `PLAN.md` to match shipped support and current next steps. | Backlog | - |
| F5 | P2 | both | Add tail-hash identity hardening for append-only logs. | Backlog | - |
| F6 | P2 | `agent-sessions` | Evaluate targeted generator APIs for baseline/index scans. | Backlog | - |

## 8. Definition Of Done

- [ ] P0 archive sync is reviewed and merged or explicitly rejected.
- [ ] P0 Gemini identity fix is reviewed and merged or explicitly rejected.
- [ ] Router and hub tests are green on the P0 branches.
- [ ] Backlog rows remain recorded without blocking P0 review.

## 9. Changelog

- 2026-07-09 - Created tracker from feedback review; started P0 archive sync and Gemini identity split.
