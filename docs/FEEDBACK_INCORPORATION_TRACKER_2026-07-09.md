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

The original P0 PRs are merged:

- `agent-sessions` PR #68: archive refresh, tracker, index identity fix, user
  insights, and PDF generation knob.
- `agent-session-router` PR #18: stable Gemini Antigravity session ids.

The active follow-up before starting the P1 queue is making rendered archive
Markdown/PDF bodies local-only by default while keeping shared metadata in Git.

## 1. Current Verified State

As of 2026-07-09 after fetching, fast-forwarding, and merging the two P0 PRs:

| Repo | Branch | Remote head | Local state |
| --- | --- | --- | --- |
| `agent-sessions` | `main` | `1260f01` | synced; active follow-up branch is `codex/local-only-archive-artifacts` |
| `agent-session-router` | `master` | `e3d085e` | synced and clean after PR #18 merge |

Archive freshness from `python .\tools\agent_archive.py status --json` after
the P0 export/index-identity fix and before the local-only artifact cleanup:

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
| D6 | Keep rendered archive Markdown/PDF bodies local-only by default; track catalog metadata in Git. | The repo should carry the portable index, not thousands of private transcript bodies. `[archive] track_artifacts = true` remains the explicit escape hatch. |

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
3. `agent-sessions`: stop tracking rendered transcript Markdown/PDF bodies by
   default; keep metadata/index files in the repo.

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
| F0 | P0 | `agent-sessions` | Check in this tracker and archive freshness sync; ignore local router diagnostics. | Done | #68 merged |
| F1 | P0 | `agent-session-router` | Populate Gemini Antigravity `metadata.session_id` from the discovered session path and cover index identity. | Done | #18 merged |
| F2 | P0 | `agent-sessions` | Make rendered archive Markdown/PDF files local-only by default; keep `archive/index.jsonl` and `archive/INDEX.md` as shared metadata. | In review | #69 |
| F3 | P0 | `agent-session-router` | Align router sidecar identity with hub catalog identity (`session_id` + `sha256`) and document local-only Markdown impact. | In review | #19 |
| F4 | P1 | `agent-session-router` | Stream Gemini JSONL parsing and file hashing instead of full-file `readFileSync`. | Next | - |
| F5 | P1 | `agent-session-router` | Split skipped vs failed export accounting. | Next | - |
| F6 | P1 | `agent-session-router` | Refresh `PLAN.md` to match shipped support and current next steps. | Next | - |
| F7 | P2 | both | Add tail-hash identity hardening for append-only logs. | Backlog | - |
| F8 | P2 | `agent-sessions` | Evaluate targeted generator APIs for baseline/index scans. | Backlog | - |

## 8. Definition Of Done

- [x] P0 archive sync is reviewed and merged or explicitly rejected.
- [x] P0 Gemini identity fix is reviewed and merged or explicitly rejected.
- [x] Router and hub tests are green on the original P0 branches.
- [ ] Local-only archive artifact follow-up is reviewed and merged or explicitly rejected.
- [ ] Router compatibility follow-up is reviewed and merged or explicitly rejected.
- [x] Next P1 rows are identified without blocking the P0 follow-up.

## 9. Changelog

- 2026-07-09 - Created tracker from feedback review; started P0 archive sync and Gemini identity split.
- 2026-07-09 - Merged hub PR #68 and router PR #18; opened hub PR #69 for the local-only artifact follow-up before starting the P1 router queue.
- 2026-07-09 - Opened router PR #19 after impact verification found the router sidecar still deduped by `session_id` alone.
