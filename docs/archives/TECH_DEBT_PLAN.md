<!--
Tracked project doc per docs/PROJECT_DOC_TEMPLATE.md.
-->

# Tech Debt Remediation Plan

> **Status:** `DONE` (archived) · **Owner:** `avidullu` · **Created:** `2026-07-06` · **Last updated:** `2026-07-06`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived` (move to `docs/archives/` when DONE)
> **Progress:** 15 of 15 landed (TD1–TD15). Project complete; issue #34 (TD10) closed by PR #40.
> **Tracking anchors:** §7 progress tracker is the source of truth; indexed in `docs/README.md`; pointer in `SESSION_HANDOFF.md`.
> **Relation to existing docs:** peer-of `docs/BASELINE_LOOP_CLOSURE.md`; complements `docs/TEST_PLAN.md`.
> **Honesty note:** each finding below is `[verified]` unless marked otherwise — all were reproduced against the working tree at commit `5d81234` (tests: 362 passed / 2 skipped, coverage 93.30%).

---

## 0. TL;DR

A full audit (pytest + coverage, ruff, mypy, manual review of every module) found the
codebase healthy at its core — 93% coverage, green default lint — but carrying
seventeen debt items. The most impactful: `pip install -e ".[dev]"` (the documented
setup) **fails outright** due to missing packaging config, there is **no CI**, `baseline.py`
is a 1,015-line god-module with a circular import, `baseline promote` can **silently
destroy hand-written content** in `baseline/global/*.md`, and the archive index has
machine-specific keys plus a local-time/UTC mismatch that both produce duplicate
records across machines. The plan below sequences fixes as small PRs: correctness
and data-loss traps first, structure second, polish last.

## 1. Problem & goal

The repo's own promoted guardrails preach verified regression gates and reviewable
increments, but the tooling that generates them is not held to that standard: setup
is broken as documented, nothing runs the tests automatically, and two code paths
can lose user data (promote rewrites, non-atomic ledger writes). Goal: every
documented command works on a fresh clone, CI enforces the advertised gates, no
pipeline step can destroy human-authored content, and the index behaves correctly
across machines.

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|----------|---------------|-------------|
| D1 | One small PR per tracker row | PROJECT_DOC_TEMPLATE convention | No omnibus cleanup PRs |
| D2 | Correctness/data-loss fixes land before structural refactors | this audit, 2026-07-06 | TD1–TD6 precede TD7+ |
| D3 | Coverage gate stays at 80 (`pyproject.toml`), CI enforces it | existing config | CI must run pytest with coverage |
| D4 | Index identity must become machine-independent (sha256-based) before more multi-machine features | audit finding 6 + `docs/MULTI_MACHINE.md` | Blocks P5 cross-agent correlation work |

## 3. Foundation — audit evidence

Audit performed 2026-07-06 on a fresh Linux checkout:

- **Install:** `python -m pip install -e ".[dev]"` fails — setuptools flat-layout
  auto-discovery finds `['config', 'archive', 'baseline', 'agent_sessions']` and
  aborts. No `[build-system]`, no package list, no console script. `[verified]`
- **Tests:** 362 passed, 2 skipped (reportlab), ~2s. Coverage 93.30%. `[verified]`
- **Coverage gaps:** `render.py` 46% (`write_pdf` body untested), `cli.py` 77%
  (lines 171–223: calibrate/promote/publish/eval/ingest/bundle dispatch never
  exercised through `main()`), `archive.py` `pdf_existing` mostly uncovered. `[verified]`
- **ruff:** 0 errors on defaults, but no `[tool.ruff]` config exists; a broader
  `--select E,W,F,I,B,UP,SIM,ARG,PTH,ANN` pass reports ~360 issues. `[verified]`
- **mypy:** 2 errors (`render.py:58-59`, missing reportlab stubs); no `[tool.mypy]`
  config. `[verified]`
- **CI:** `.github/` does not exist; no pre-commit config. `[verified]`

## 4. Design / remediation detail

### Tier 1 — Correctness & data-loss traps

1. **Packaging (TD1).** Add `[build-system]`, `[tool.setuptools] packages = ["agent_sessions", "agent_sessions.sources"]`,
   `[project.scripts] agent-archive = "agent_sessions.cli:main"`; drop the
   `sys.path` hack in `tools/agent_archive.py:9-11`. Note `cli.py:14`
   (`REPO_ROOT = Path(__file__).resolve().parents[1]`) assumes the package lives
   inside the data repo — derive repo root from cwd or `--repo-root` instead.
2. **CI + toolchain config (TD2, TD3).** Add ruff/mypy to dev extras with committed
   `[tool.ruff]`/`[tool.mypy]` config (reportlab `ignore_missing_imports`); add a
   GitHub Actions workflow running pytest+coverage, ruff, mypy on push/PR.
3. **Promote data loss (TD4).** `promote_predictions` (`baseline.py:977-978`)
   replaces a global file having no marker blocks with a bare header, and
   `upsert_promoted_content` (`baseline.py:921-928`) rebuilds files as
   `header + sorted(blocks)`, dropping any manual prose outside
   `<!-- baseline:begin/end -->` markers. Fix: preserve non-marker content, or
   refuse to rewrite files containing unmarked content without `--force`.
4. **Non-atomic ledger writes (TD5).** `upsert_ledger` (`baseline.py:413-431`)
   rewrites `prediction-ledger.jsonl` in place; a crash mid-write destroys
   calibration history. Fix: temp file + `os.replace`.
5. **Timezone stem bug (TD6).** `archive.py:321` uses naive local time for the
   `YYYYMMDD` archive-stem prefix while `render.py:53` uses UTC — the same session
   exported near midnight or from different-timezone machines yields different
   stems → duplicate archive files. Fix: UTC everywhere.

### Tier 2 — Index integrity & error handling

6. **Index identity/lifecycle (TD7).** `merge_index_records` (`archive.py:138-163`)
   keys on `(source, source_file)`; absolute paths are machine-specific
   (`C:\Users\...` vs `\\wsl.localhost\...` vs `/home/...`), so the same logical
   session duplicates across machines. Stale records are never pruned; changed
   digests orphan old `.md` files. Fix: sha256-based identity, `prune`/`gc`
   command, POSIX-normalized repo-relative paths written once at index time
   (deletes the nine scattered `.replace("\\", "/")` call sites).
7. **Inconsistent JSONL error policy (TD8).** `archive.py:151,232` and
   `baseline.py:335` crash with raw `json.JSONDecodeError` on one corrupt line
   while `utils.jsonl_objects:23-26` silently skips. Unify on one tolerant,
   warning-emitting reader; de-duplicate the copy-pasted `load_index_records`
   (`archive.py:223-233` ≡ `baseline.py:326-336`).
8. **Silent failures (TD9).** Unknown `--source` selectors match nothing silently
   (`archive.py:64-68`); unresolvable `{wsl_home}` becomes a sentinel path that
   quietly fails `root.exists()` (`path_templates.py:38-42`, `archive.py:35-36`);
   `config.load_source` raises bare `KeyError`; library code exits the process via
   scattered `raise SystemExit`. Add warnings and typed errors.

### Tier 3 — Structure & consistency

9. **Split `baseline.py` (TD10).** 1,015 lines mixing settings, scaffold templates,
   IO, signal scanning, prediction generation, report rendering, and promotion;
   circular import with `baseline_calibration` worked around by a function-level
   import at `baseline.py:144`. Split into `baseline_settings` / `baseline_predictions`
   / `baseline_promote` / `baseline_report` with a shared `baseline_types` module.
10. **CLI restructure + tests (TD11, TD12).** Replace the 107-line `build_parser`
    monolith and the `main()` if-chain with per-command `set_defaults(func=...)`
    registration; add parametrized `main([...])` integration tests for the six
    untested baseline subcommands and real PDF-path tests (make reportlab a test
    extra).
11. **Config-drive `baseline_eval` (TD13).** Gates hardcode
    `badminton-highlight-indexer` (`baseline_eval.py:70`), doc names, magic
    thresholds, and `evaluate_e6` builds its own `ArchiveConfig` ignoring
    `--config` (`baseline_eval.py:141-146`). Drive from `config/baseline.toml`;
    pass `ArchiveConfig` uniformly.
12. **Consistency sweep (TD14).** Frozen `Prediction` + `dataclasses.replace`
    everywhere (today `apply_feedback` mutates, `apply_calibration_loop` copies);
    single `parse_verdict()` helper replacing five re-implementations; drop the
    unreachable pre-3.11 tomllib guard (`config.py:9-12`); cache/platform-guard
    the `wsl.exe` subprocess calls in `path_templates.py:56-70`; docstrings on the
    public API (notably `utils.text_from_content`, the heart of every extractor).
13. **Performance (TD15, optional).** `status` sha256-hashes every visible file on
    every call (`archive_status.py:80-84`) and export re-extracts everything
    (`archive.py:94`). Add (size, mtime) short-circuits against the index record.
    Fine at ~3k sessions today; needed before tens of thousands.

## 5. Threat model / risk table

| Risk | Mitigation |
|------|------------|
| Promote refactor (TD4) changes generated-file layout and breaks `baseline publish` parsing | Golden-file tests over `baseline/global/*.md` round-trips before touching the writer |
| Index re-keying (TD7) invalidates existing `archive/index.jsonl` records | One-time migration that maps old keys → sha256 identity; `status` must report unchanged counts on all machines |
| CI (TD2) fails on the ~360 broader-ruleset ruff findings | Land config with today's rule set green, ratchet rules up in follow-up PRs |

## 6. Honest limits — what this does NOT do

- Does not add features (search, new extractors, replay — see the self-improving
  replay-loop issue for the latter).
- Does not raise the coverage gate above 80 or chase 100% on `write_pdf` layout.
- TD15 performance work is deferred until the archive size demands it.

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated. **One small PR per row.**

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| TD1 | Packaging: build-system, packages, console script, drop sys.path hack | — | No | ☑ | #28 |
| TD2 | Dev extras + committed ruff/mypy config matching README claims | TD1 | No | ☑ | #28 |
| TD3 | GitHub Actions CI: pytest+cov, ruff, mypy | TD2 | No | ☑ | #28 |
| TD4 | Content-preserving (or `--force`-guarded) `baseline promote` | — | No | ☑ | #31 |
| TD5 | Atomic ledger writes (temp file + `os.replace`) | — | No | ☑ | #31 |
| TD6 | UTC-consistent archive stems | — | No | ☑ | #31 |
| TD7 | Index identity: session-id keys, POSIX paths at write time, `prune` command | TD6 | No | ☑ | #33 |
| TD8 | Unified tolerant JSONL reader; de-dupe `load_index_records` | — | No | ☑ | #33 |
| TD9 | Warnings/typed errors for unknown sources, missing WSL roots, bad config | — | No | ☑ | #33 |
| TD10 | Split `baseline.py`; break `baseline`↔`baseline_calibration` cycle | TD4 | No | ☑ | #40 (issue #34) |
| TD11 | CLI restructure: per-command registration, portable repo-root | TD1 | No | ☑ | #28 + #37 |
| TD12 | Integration tests: six baseline subcommands via `main()`, PDF paths | TD11 | No | ☑ | #35 |
| TD13 | Config-driven `baseline_eval` gates; uniform `ArchiveConfig` API | TD10 | No | ☑ | #37 |
| TD14 | Consistency sweep: frozen Prediction, parse_verdict, dead code, docstrings | TD10 | No | ☑ | #37 |
| TD15 | Incremental export/status via (size, mtime) short-circuit | TD7 | Optional | ☑ | #38 |

**All fifteen deliverables are merged.** TD11's two halves shipped across #28
(`--repo-root` + `sys.path` removal) and #37 (per-command `set_defaults`
registration); TD10 landed in #40, splitting `baseline.py` (1,044 → 332 lines)
into `baseline_types` / `baseline_settings` / `baseline_predictions` /
`baseline_report` / `baseline_promote` and breaking the
`baseline`↔`baseline_calibration` cycle, with import-hygiene regression tests.

**Project complete.** Remaining related work lives outside this tracker: #32
(one-time index backfill + `regenerate` feature).

## 8. Open questions — owner / external

- ~~Owner: should TD7's migration also rewrite existing archive filenames?~~
  Resolved 2026-07-06: re-key index only; one-time filename backfill + a
  `regenerate` feature tracked in issue #32.
- Owner: is the broader ruff rule set (`E501` line length etc.) worth adopting, or
  keep defaults + isort/bugbear only? *(Carried forward as an open preference —
  current config stays defaults-plus-line-length-120.)*

## 9. Definition of done

- [x] `pip install -e ".[dev]"` succeeds on a fresh clone; `agent-archive --help` works. *(#28)*
- [x] CI runs pytest (coverage ≥ 80), ruff, and mypy green on every PR. *(#28)*
- [x] `baseline promote` cannot delete hand-written content — the rewriter is
  content-preserving outside marker blocks, stronger than the `--force` guard
  originally sketched. *(#31)*
- [x] Ledger writes are crash-safe. *(#31)*
- [x] Two machines exporting the same session produce one index record (session-id
  merge identity; existing-file backfill deferred to #32). *(#33)*
- [x] `baseline.py` < 400 lines (332) with no circular imports, enforced by
  import-hygiene tests. *(#40)*
- [x] All six baseline subcommands covered by CLI-level tests. *(#35)*

## 10. References

**Internal:** `pyproject.toml`, `tools/agent_archive.py`, `agent_sessions/{archive,baseline,baseline_types,baseline_settings,baseline_predictions,baseline_report,baseline_promote,baseline_eval,baseline_calibration,cli,render,config,path_templates,archive_status,utils}.py`, `docs/TEST_PLAN.md`, `docs/MULTI_MACHINE.md`.
**External:** none required.

### Changelog
- `2026-07-06` — Initial audit and plan drafted.
- `2026-07-06` — TD1–TD3 landed (#28); tracker updated (#36).
- `2026-07-06` — TD4–TD6 (#31), TD7–TD9 (#33), TD12 (#35) landed.
- `2026-07-06` — TD11/TD13/TD14 (#37) and TD15 (#38) landed; tracker to 14/15 (#39).
- `2026-07-06` — TD10 landed (#40, closes #34). 15/15 complete; status DONE; doc archived.
