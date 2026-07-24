# First-User Setup UX

> **Status:** `DONE` - setup UX MVP complete; optional `doctor` command deferred. **Owner:** `avidullu`. **Created:** `2026-07-07`. **Last updated:** `2026-07-07`
> **Lifecycle:** `DRAFT -> IN PROGRESS -> DONE -> archived`
> **Tracking anchors:** Section 7 is the source of truth; indexed in `docs/README.md`; pointer in `SESSION_HANDOFF.md`.
> **Relation to existing docs:** extends `README.md`, `docs/MULTI_MACHINE.md`, and `docs/AUTOMATION.md`; folds issue #18 into issue #42.
> **Honesty note:** claims marked `[verified]` were checked against `origin/main` at `013170b`; `[design]` items are scoped but not implemented yet.

---

## 0. TL;DR

Make a first-user or new-machine setup journey boring in the best way: the user
should know which commands to run, which files normally change, what skipped
inventory sources mean, how Markdown/PDF export behaves, and what to do after a
successful export or baseline suggestion. The approved MVP folds issue #18 into
issue #42, documents the boundary to issue #32, and defers a `doctor` command to
a later code slice.

## 1. Problem & goal

**Problem:** issue #42 reports that the core setup path works, but the user has
to infer expected outputs, optional PDF behavior, skipped inventory-source
meaning, and next review steps. Issue #18 asks for a new-computer setup and sync
validation checklist, which is the same workflow from the next-machine angle.

**Goal:** a first user can run discovery, status, export, baseline scaffold, and
baseline suggest with clear expectations and safe git/sync boundaries.

**Good looks like:**

1. README quick start names expected command outputs and changed paths.
2. New-machine setup has a copy/paste checklist for Windows and WSL/Linux.
3. Inventory-only Copilot/ZAI sources are documented as expected skips.
4. PDF support is optional, visible, and easy to verify.
5. The project boundary to archive backfill/regenerate (#32) is explicit.

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|---|---|---|
| D1 | Treat #42 as the active umbrella. | Owner approval, 2026-07-07 | This tracker is scoped around first-user setup feedback. |
| D2 | Fold #18 into this project. | Issue scan, 2026-07-07 | New-machine setup is part of the MVP docs surface. |
| D3 | Keep #32 separate except for boundary notes. | Issue scan, 2026-07-07 | Do not bundle destructive archive backfill/regenerate work into setup UX. |
| D4 | Docs and trackers land before code execution. | Owner approval, 2026-07-07 | First PR is documentation-only; code polish follows after docs are merged. |
| D5 | `doctor`/`setup` command is stretch. | Issue #42 optional acceptance criterion | Implement only after docs prove the desired checks and wording. |

## 3. Foundation

Issue scan on 2026-07-07:

| Issue | Classification | Reason |
|---|---|---|
| #42 | Primary | First-user installation journey feedback and acceptance criteria. |
| #18 | Fold in | Same setup journey, focused on new-computer validation and sync. |
| #32 | Boundary/risk | Important data-integrity feature, but too broad for setup UX MVP. |
| #19 | Separate | Provenance traces for baseline suggestions, not setup. |
| #23 | Separate | Handoff mining feature, not setup. |
| #25 | Separate | Replay loop feature, not setup. |
| #26 | Separate | Compounding wiki layer, not setup. |

Repo state checked on `origin/main` at `013170b`:

- `README.md` already has a quick start and agent-assisted setup prompt.
- `docs/MULTI_MACHINE.md` already explains merge-aware index behavior.
- `docs/AUTOMATION.md` already documents scheduled export scripts.
- `docs/archives/TECH_DEBT_PLAN.md` marks TD1-TD15 complete and names #32 as follow-up.

## 4. Design / documentation map

| Surface | Role |
|---|---|
| `README.md` | Fast path: commands, expected outputs, PDF/inventory notes, next review steps. |
| `docs/NEW_MACHINE_SETUP.md` | Copy/paste bootstrap and validation checklist for additional computers. |
| `docs/MULTI_MACHINE.md` | Conceptual convergence model plus link to the practical checklist. |
| `docs/AUTOMATION.md` | Scheduled sync details after manual setup is validated. |
| `docs/README.md` | Docs index pointer. |
| `SESSION_HANDOFF.md` | Resume pointer for active project state. |

## 5. Threat model / risk table

| Risk | Mitigation |
|---|---|
| A first user commits local config or raw logs. | Reiterate that `sources.toml` and `raw/` are ignored/local unless intentionally force-added. |
| Inventory-only sources look like exporter failures. | Explain skipped inventory sources in README and setup checklist. |
| PDF behavior looks inconsistent across machines. | Make `reportlab` optionality explicit and provide a verification command. |
| Setup docs imply #32 backfill/regenerate exists. | Link #32 as future data-integrity work, not a setup step. |
| A large export creates a noisy git status. | Add explicit `git status --short archive/index.jsonl archive/INDEX.md docs/DISCOVERY.md` and staging guidance. |

## 6. Honest limits

- This project does not implement archive backfill or `regenerate` from #32.
- This project does not add hosted/cloud imports or semantic search.
- This project does not auto-enable scheduled sync; the user must choose a sync
  mode and approve archive commits.
- The initial docs slice does not add a `doctor` command.

## 7. Deliverables & progress tracker

Legend: Todo, In progress, Done, Stretch. One small PR per row where code changes
are needed.

| ID | Deliverable | Depends on | Gated? | Status | PR |
|---|---|---|---|---|---|
| P0 | Add this tracked project doc and index/handoff pointers. | - | No | Done | #43 |
| P1 | README documents expected outputs for discovery, status, export, baseline scaffold, and baseline suggest. | P0 | No | Done | #43 |
| P2 | README explains Markdown vs PDF behavior and optional `reportlab` support. | P0 | No | Done | #43 |
| P3 | README/setup docs explain inventory-only skipped sources. | P0 | No | Done | #43 |
| P4 | README gives concise post-export and post-baseline next steps. | P0 | No | Done | #43 |
| P5 | Add new-machine setup and sync validation checklist. | P0 | No | Done | #43 |
| P6 | Add troubleshooting for noisy git status, dirty/diverged git state, missing WSL paths, missing PDF support, and local `sources.toml`. | P5 | No | Done | #43 |
| P7 | Optional `doctor` or `setup` command for dependency/source checks. | P1-P6 | Yes | Stretch | - |
| P8 | Document #32 boundary: archive backfill/regenerate remains separate. | P0 | No | Done | #43 |
| P9 | Export command prints a concise next-steps summary and tests cover skipped inventory/PDF/dry-run branches. | P1-P6 | No | Done | #44 |

## 8. Open questions

1. Should the stretch `doctor` command be read-only only, or should it offer
   guided fixes such as creating `sources.toml`?
2. Should first-run setup recommend `--pdf` by default now that dev extras include
   `reportlab`, or keep PDFs explicitly optional for speed?

## 9. Definition of done

- [x] P0-P6 and P8 are merged.
- [x] README and setup checklist make the #42 acceptance criteria easy to verify.
- [x] New-machine instructions cover Windows and WSL/Linux paths and validation.
- [x] Optional code slice, if taken, has full pytest coverage, ruff, and mypy clean.

## 10. References

**Internal:** `README.md`, `docs/MULTI_MACHINE.md`, `docs/AUTOMATION.md`,
`docs/archives/TECH_DEBT_PLAN.md`, `docs/PROJECT_DOC_TEMPLATE.md`.

**GitHub issues:** #42, #18, #32, #19, #23, #25, #26.

### Changelog

- `2026-07-07` - Created after owner approved the recommended scope.
- `2026-07-07` - Sent P0-P6/P8 docs for review in PR #43.
- `2026-07-07` - PR #43 merged; P9 CLI summary polish completed in PR #44.
