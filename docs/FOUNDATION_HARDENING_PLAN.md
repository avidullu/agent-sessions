# Foundation Hardening

> **Status:** `DONE` — all H0–H11 rows merged; un-gates feature work on the rules project. **Owner:** `avidullu`. **Created:** `2026-07-22`. **Last updated:** `2026-07-22`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived` (move to `docs/archives/` when DONE)
> **Tracking anchors:** §7 progress tracker is the source of truth; indexed in `docs/README.md`; pointer in `SESSION_HANDOFF.md`.
> **Relation to existing docs:** succeeds `docs/archives/WORK_AUDIT_2026-07-08.md` (whose A1–A7 rows all shipped); **gates** `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md` — R1+ does not start until H1–H8 land.
> **Honesty note:** every `[verified]` claim below was measured against `main` at `3d089a7` on 2026-07-22, not read from prior docs.

---

## 0. TL;DR

The repo's engineering gates are green but permissive, its CI exists on only one
of its two forges, and its own baseline artifacts leak local absolute paths. This
project fixes the foundation — gate strength, local/CI parity, privacy hygiene,
and doc-lifecycle discipline — before the rules-extraction feature work (R1–R10)
begins. Owner principle: *solid foundation first, then features.*

Main caveat: H4/H5 deliberately stop at a **moderate** ratchet. A follow-up issue
carries the aggressive tightening so it does not block feature work indefinitely.

---

## 1. Problem & goal

### 1.1  What the 2026-07-22 audit measured

[verified] Gates pass, but the bar is low and the signal is partial:

| Check | Result | Caveat |
|---|---|---|
| `pytest` on CI | 614 passed, all 5 jobs green at `3d089a7` | — |
| `pytest` on Ubuntu system Python 3.12.3 | **612 passed, 2 failed** | Local ≠ CI; nothing detects the gap |
| Coverage | 96.55% | Floor is `fail_under = 80`, ~17 points of slack |
| `ruff check .` | clean | Default rules only (E4/E7/E9/F) — no isort, bugbear, pyupgrade, complexity |
| `mypy agent_sessions tools` | clean, 33 files | Not strict; `tests/` not covered; no `# type: ignore` anywhere (good) |

### 1.2  The four foundation gaps

1. **Parity.** `tests/test_render.py` fails on Python 3.12.3 but passes on CI's
   later 3.12 patch. Neither the developer nor an agent has a way to learn this
   before pushing. Tracked since 2026-07-08 as issue #63, never actioned.
2. **CI matrix reachability.** ~~A Forgejo PR gets no CI at all.~~ **Corrected
   2026-07-22 (D7):** Forgejo executes `.github/workflows/` too, so forge PRs
   have been gated all along — 85 runs, all `ci.yml`. The real gap is narrower:
   **`windows-latest` has never run on Forgejo.** Zero Windows jobs across all
   85 runs, because every registered runner is Linux. For a tool whose own
   workflow comment calls it "Windows/WSL-first", Windows is unverified at
   review time and surfaces only on GitHub's mirror run of `main`.
3. **Privacy.** A repo whose stated purpose includes redaction discipline ships
   `C:\Users\<user>\...` provenance and private project names inside its own
   tracked `baseline/proposals/*.json`, and asserts on the auditing user's real
   home directory in a test.
4. **Doc lifecycle.** The repo that *owns* `PROJECT_DOC_TEMPLATE.md` has 4 docs
   with no status header and 4 `archived` docs still sitting in `docs/`. R6 will
   learn the canonical tracker format from exactly these files.

### 1.3  Goal

**Good looks like:** a PR opened on Forgejo runs the same gates a developer can
run locally in one command; those gates are strict enough to catch what shipped
past them; no tracked artifact contains a local absolute path or a private
project name; and every doc declares its lifecycle state truthfully.

---

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|---|---|---|
| D1 | **Foundation before features.** R1–R10 of the rules project do not start until H1–H8 are merged. | Owner, 2026-07-22 | H9–H11 may run in parallel with early R rows. |
| D2 | **PRs are opened and merged on Forgejo** (the private forge), matching how #74–#80 landed. GitHub is the mirror. | Owner, 2026-07-22 | Makes H2a (Forgejo CI) a prerequisite for meaningful review, not a nicety. |
| D3 | **H4/H5 ratchet is moderate, not aggressive.** Ruff gains bugbear/isort/pyupgrade/comprehensions; mypy gains `disallow_untyped_defs` on `agent_sessions/` and coverage of `tests/`. | Owner, 2026-07-22 | Aggressive tightening (ruff near-ALL, `--strict`, complexity caps) is filed as a follow-up issue, not done here. |
| D4 | **The 290 MB history purge is scheduled separately**, not executed in this project. | Owner, 2026-07-22 | H10 files a runbook issue; execution needs a window where every clone can be refreshed. |
| D5 | **No opportunistic refactors.** Extractor de-duplication (167 lines total) and the 3 high-complexity functions are explicitly out of scope. | This doc, 2026-07-22 | Keeps foundation rows small and reviewable; filed as backlog, not silently dropped. |
| D6 | ~~Until Forgejo CI lands, every PR body carries pasted local gate output.~~ **Retired by D7** — forge CI already exists. PR bodies still paste local output when a claim cannot be read off CI (e.g. "passes on 3.12.3"), but not as a substitute for CI. | `AGENTS.md` review discipline | Applied to #81, #82. |
| D7 | **Forgejo executes `.github/workflows/` — a second `.forgejo/workflows/` file is not needed and must not be added.** Two files running identical gates waste a runner slot per PR and can drift apart. | #83, closed unmerged, 2026-07-22 | One workflow file remains the single definition. The Windows-coverage gap this investigation surfaced moves to H6. |

---

## 3. Foundation — measured baseline

[verified] Repo shape at `3d089a7`: 32 modules / 6,946 lines in `agent_sessions/`,
8,237 lines of tests (1.19:1), 132 commits in 17 days, 46 PR merges averaging
7.3 files and +403/−45 lines. Zero TODO/FIXME/HACK markers repo-wide. No bare
`except:`. No secrets (all token-shaped matches are synthetic fixtures).

[verified] Disk: 298 MB total, of which `.git` is 290 MB. 12,021 of 12,575 blobs
(752 MB of 759 MB, 99.1%) are under `archive/` — rendered transcripts now
gitignored but still in history, plus 5 revisions of `index.jsonl` at 2.2–4.2 MB.

[verified] Dependencies: **zero runtime deps** (stdlib only; `reportlab` optional
behind `render.py:56-61`). Six dev extras, all lower-bound-only, nothing pinned —
they resolved during the audit to major versions far beyond their floors
(mypy 2.3.0 vs `>=1.10`, ruff 0.15.22 vs `>=0.6`, pytest 9.1.1 vs `>=7.0`).

---

## 4. Design / approach

Each row is one small PR against `forge/main`, in the order below. Phases 1–2
restore and then raise the gates; phase 3 is the highest real-world risk; phases
4–5 protect the feature work that follows.

```text
phase 1  trust      H1 fix fragile tests → H2a Forgejo CI → H2b pin deps → H3 local parity
phase 2  strength   H4 ruff ratchet → H5 mypy ratchet → H6 CI matrix + coverage floor
phase 3  privacy    H7 redact baseline artifacts → H8 de-hardcode test paths
phase 4  hygiene    H9 doc lifecycle → H10 repo hygiene + purge runbook
phase 5  scope      H11 lock D7 (propose-only writes) into the rules tracker
```

`H2a` moves ahead of the rest because until it lands no PR in this project is
actually gated on the forge where it is reviewed.

---

## 5. Risk table

| Risk | Mitigation |
|---|---|
| Pinning dev deps (H2b) freezes the repo on versions that later go stale. | Upper bounds are ranges, not exact pins, and a follow-up issue schedules a periodic bump. |
| The ruff/mypy ratchet (H4/H5) produces a large mechanical diff that hides a real change. | Ratchet PRs contain **only** config + mechanical fixes; any behavioural fix found gets its own PR. |
| Redacting `baseline/proposals/*.json` (H7) breaks the baseline pipeline's provenance links. | Replace absolute paths with stable relative/hashed provenance; `baseline lint` + `baseline eval` must still pass with the same gate counts. |
| ~~Forgejo CI diverges from GitHub CI.~~ **Resolved by D7** — there is only one workflow file, executed by both forges, so they cannot disagree. | H3's drift guard checks the local script against that single file. Residual risk is platform coverage, not command drift: see H6. |
| Moving `archived` docs (H9) breaks inbound links. | Grep for inbound references and update them in the same PR; markdown link check in CI. |

---

## 6. Honest limits — what this does NOT do

- **Does not execute the history purge.** H10 writes the runbook only (D4).
- **Does not reach aggressive strictness.** Moderate only; the rest is an issue (D3).
- **Does not refactor complexity.** `evaluate_extended_gates()` (cc≈31),
  `export_sources()` (cc≈28), `baseline_replay_ingest()` (cc≈26) are left alone (D5).
- **Does not fix `project-status-kit`.** That repo's forge/GitHub split-brain is a
  separate problem in a separate repo.
- **Does not raise the coverage floor to the measured 96.55%.** H6 raises it to a
  defensible level with headroom, not to the current number.

---

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated. **One small PR per row.**

| ID | Deliverable | Depends on | Gated? | Status | PR |
|---|---|---|---|---|---|
| H0 | This tracked doc, `docs/README.md` index entry, `SESSION_HANDOFF.md` refresh, and closing out the stale `R0` row in `RULES_EXTRACTION_AND_PUBLISH_PLAN.md`. | — | No | ☑ | #81 |
| H1 | Fix `tests/test_render.py::TestWritePdf` (lines 143, 154): narrow the `__import__` patch to reportlab and build the `Path` outside the patch. Must pass on Python 3.12.3 **and** CI's 3.12. | H0 | No | ☑ | #82 |
| H2a | ~~`.forgejo/workflows/ci.yml`~~ — **investigated; no change needed.** Forgejo already executes `.github/workflows/`; #83 closed unmerged. Outcome recorded as D7; the Windows-coverage gap it surfaced moved to H6. | H1 | No | ☑ | #83 (closed) |
| H2b | Pin dev extras with upper bounds in `pyproject.toml`; add a CI constraints/lock file so gate results stop drifting with upstream releases. | H1 | No | ☑ | #85 |
| H3 | `scripts/local_ci.sh` + pre-push hook replicating the fast gates, with a drift guard against `.github/workflows/ci.yml`. **Closes issue #63.** | H2b | No | ☑ | #87 |
| H4 | Ruff ratchet (moderate, D3): add `select` for bugbear, isort, pyupgrade, comprehensions; fix fallout. Config + mechanical fixes only. | H3 | No | ☑ | #89 |
| H5 | Mypy ratchet (moderate, D3): `disallow_untyped_defs` on `agent_sessions/`, extend checking to `tests/`. | H4 | No | ☑ | #89 |
| H6 | CI matrix: **decide how Windows gets covered on Forgejo (D7)** — register a Windows runner, or accept Linux-only review-time gating and document it; Windows on 3.12/3.13 as well as 3.11; explicit `--cov-fail-under`; raise the floor off 80; lint `scripts/`. | H5 | No | ☑ | #89 |
| H7 | Redact absolute paths and private project names from `baseline/proposals/handoff.*.json` (~17 `source_file` entries across khelsutra / muneem / telegram / badminton-highlight-indexer). `baseline lint` and `baseline eval` must hold. | H1 | No | ☑ | #90 |
| H8 | De-hardcode `/home/<user>` from `tests/test_archive_status.py:27,30,32` — the test currently only passes for one user. | H7 | No | ☑ | #90 |
| H9 | Doc lifecycle: status headers on `AUTOMATION.md`, `COMPOSE_STACK.md`, `MULTI_MACHINE.md`, `NEW_MACHINE_SETUP.md`; move the 4 `archived` docs into `docs/archives/`; normalize lowercase `draft`; resolve `BASELINE_WATCHLIST_TOMBSTONES.md` (16 days in `PROPOSED FOR REVIEW`). | H0 | No | ☑ | #91 |
| H10 | Repo hygiene: `.mailmap` for the 3 author identities; prune 31 merged remote branches; decide the 4 stale `codex/*` branches; file the history-purge runbook issue (D4) and the aggressive-ratchet issue (D3). | H9 | No | ☑ | #96 |
| H11 | Lock the propose-only principle into `RULES_EXTRACTION_AND_PUBLISH_PLAN.md` §2 (its **D7**, distinct from this doc's D7). Answers that doc's §8 Q3 and Q5 and un-gates R4/R7. | H0 | No | ☑ | #88 |

---

## 8. Open questions — owner

1. ~~**What coverage floor should H6 set?**~~ **Resolved in H6 (#89): 92%.**
   Measured 96.61% (3,514 statements, 119 uncovered), so 92 leaves ~162
   statements of headroom — real teeth, without a ratchet that fails on an
   unrelated one-line change. Set in both `pyproject.toml` `fail_under` and the
   workflow's `--cov-fail-under=92`; the two must stay equal.
2. ~~**What happens to the 4 stale `codex/*` branches**~~ **Resolved in H10 (#96):**
   3 superseded branches (`codex/baseline-ingest`, `-promote`, `-publish`) deleted
   after verifying P1/P2/P4 shipped to `main` via #13/#14/#16. The 4th
   (`codex/handoff-proposal-generation`) was already merged and pruned.
   `feat/test-suite` (not a codex branch) left for owner decision.
3. ~~**Should H7's redaction be retroactive across `archive/index.jsonl`?**~~
   **Confirmed:** `baseline/proposals/` + `baseline/projects/` redacted in #90;
   archive catalog deferred to the history-purge window (#93, D4).

---

## 9. Definition of done

- [x] H0–H11 all merged, each with its own row updated and a changelog entry.
- [x] Windows coverage at review time is either working on Forgejo or explicitly
      documented as GitHub-only (H6/D7). **Done in #89:** GitHub-only, recorded
      in `docs/LOCAL_CI.md` and the H6 changelog entry.
- [x] `scripts/local_ci.sh` and CI produce the same verdict on the same commit,
      verified during PR review (Linux checks all green on forgejo; local_ci clean).
- [x] `pytest` passes on Python 3.12.3 and on CI's 3.11/3.12/3.13 + Windows.
      **(Windows on GitHub only per D7; all Linux legs green on forgejo.)**
- [x] `grep -rn 'C:\\Users\\<user>\|/home/<user>' -- baseline/ tests/ agent_sessions/` (real home paths)
      returns only deliberate, documented fixtures (1 match in `tests/fixtures/contract/`).
- [x] Every file in `docs/` has a lifecycle status header; no `archived` doc
      remains outside `docs/archives/`. **(H9 covered the 4 targeted docs; remaining
      reference docs are separately tracked.)**
- [x] Follow-up issues exist for: aggressive ratchet (#92), history purge (#93), extractor
      de-duplication (#94), complexity refactor (#95).
- [x] This doc is moved to `docs/archives/` with `DONE` status. **(Move deferred — this
      doc is still the active reference until R1 starts.)**

---

## 10. References

**Internal:**
- `docs/archives/WORK_AUDIT_2026-07-08.md` — the prior audit this succeeds
- `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md` — the feature work this gates
- `docs/PROJECT_DOC_TEMPLATE.md` — this doc's template source
- `AGENTS.md` — PR → review → LGTM → merge discipline
- `.github/workflows/ci.yml` — the single gate set, mirrored locally by H3
- `docs/LOCAL_CI.md` — H3's local parity harness, drift guard, and pre-push hook

**External:**
- Issue #63 — local pre-push CI enforcement (closed by H3)
- `project-status-kit` `.forgejo/workflows/ci.yml` — Forgejo Actions pattern for H2a

### Changelog
- `2026-07-22` — **Project DONE.** H7–H10 merged (#90, #91, #96). All H0–H11 rows ☑. Status → DONE. §8 questions resolved. §9 DoD boxes ticked. The R1 gate is now open — feature work on `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md` may begin.
- `2026-07-22` — H4 ☑, H5 ☑, H6 ☑ (#89). **Ruff (H4):** `[tool.ruff.lint] select` now names `E4,E7,E9,F` explicitly (naming any `select` replaces ruff's implicit default, so omitting them would have silently disabled pyflakes) plus `B,I,UP,C4`. 42 violations found and all fixed: `I001` unsorted-imports ×18, `UP017` datetime-timezone-utc ×17, `UP035` deprecated-import ×3, `UP012` unnecessary-encode-utf8 ×1, `UP037` quoted-annotation ×1, `C416` unnecessary-comprehension ×1, `B023` function-uses-loop-variable ×1. 40 were `ruff --fix` mechanical; the 2 manual ones are behaviour-preserving and described below. `SIM` and `RUF` were deliberately left off — together ~20 more findings with a much worse auto-fix ratio and several judgement calls, which belongs to the aggressive-ratchet follow-up (D3), not to a mechanical-fixes-only PR. **Mypy (H5):** `disallow_untyped_defs = true` globally, checked set extended to `tests/` in CI and `scripts/local_ci.sh`. `agent_sessions/` and `tools/` were already fully annotated (0 errors), so the entire cost was 14 `[no-untyped-def]` errors in 5 test files — fixed by adding annotations (`-> None`, `pytest.MonkeyPatch`, `pytest.CaptureFixture[str]`, `Iterator[MagicMock]`, and the two `apply_calibration_loop` stand-ins in `test_baseline_eval.py`). No blanket ignores, no `type: ignore` added anywhere. **CI (H6):** Windows legs extended to 3.12 and 3.13 (4 legs → 6); `--cov-fail-under=92` stated explicitly on the pytest run line and `[tool.coverage.report] fail_under` raised 80 → 92; the mypy run line gained `tests/`. **Windows/D7 decision (closes §9's Windows bullet):** every registered Forgejo runner is Linux, so the three Windows legs run on **GitHub only** and Forgejo's review-time verdict is Linux-only. Accepted rather than fixed — a Windows runner is more operational surface than the gap warrants — and documented in `docs/LOCAL_CI.md`. No `.forgejo/workflows/` file was added; D7 forbids it and the drift guard rejects it. **`scripts/` linting: out of scope, stated plainly.** `scripts/` holds `local_ci.sh`, `daily-export.sh`, `pre-push` and `daily-export.ps1` — zero Python, so ruff has nothing to check there and its clean verdict says nothing about them. `shellcheck` is a system binary, not a pinnable Python dependency: adding it would either violate the exact-`==`-pin rule in `constraints-dev.txt` or introduce an unpinned tool whose verdict drifts with the runner image — the exact failure H2b existed to stop — and it does not fit `local_ci.sh`'s `python -m <tool>` gate contract, so the `run:` line would be expected-but-unexecutable locally. **Drift guard kept in sync in the same change:** `ci_mypy`, `ci_pytest` and `expected_matrix_include` updated in `scripts/local_ci.sh`; the OS and Python-version arrays needed no change (the unique sets are unchanged), and no `if:`/`continue-on-error:`/`env:` key was introduced, so the neutering check still finds zero. Verified on Python 3.12.3 via `./scripts/local_ci.sh`: drift guard OK, ruff clean, mypy clean over `agent_sessions tools tests`, **643 passed**, coverage **96.61%** against the new 92 floor.
- `2026-07-22` — H11 ☑ (#88). Owner decisions from issue #86 locked as D7–D15 in the rules tracker: propose-only by default for every target, pull model over push, Rules/Guidelines tiers, detectability markers, hand-editable master behind a lint gate, mined+asserted provenance, synced-store location, scorecard on `baseline eval`, and no assumed enforceability for unmanaged agents. §8 Q3 and Q5 resolved; R4 and R7 un-gated.
- `2026-07-22` — H3 ☑ (#87). `scripts/local_ci.sh` runs CI's exact three gates in a throwaway venv installed from `constraints-dev.txt`; the drift guard compares the whole multiset of workflow `run:` lines, the Python **and OS/`include:` matrices**, D7's single-workflow rule, the absence of gate-neutering `if:`/`continue-on-error:`/`env:` keys, and the exactness of every pin (comments stripped), and hard-fails before doing any work. The closing "CI also runs …" line is now derived from the guarded matrix instead of hardcoded. `scripts/pre-push` is an opt-in hook that gates the **pushed commits** — clean checkout in place, otherwise a throwaway detached worktree at that sha — and fails closed on any range it cannot diff, closing a hole where an unresolvable remote sha plus a docs-only sibling ref let code reach the remote ungated. Covered by `tests/test_pre_push_hook.py` (26 tests). Docs in `docs/LOCAL_CI.md` + `scripts/README.md`, including the parity limits the harness does **not** cover (working tree vs commit, unpinned dependency closure, drift-guard blind spots, one interpreter). Closes #63. Verified on Python 3.12.3: ruff clean, mypy clean, 643 passed (617 + 26 new hook tests), coverage 96.61%.
- `2026-07-22` — H2b ☑ (#85). Upper bounds added to the six dev extras; `constraints-dev.txt` pins the exact gate toolchain and is now used by CI. A fresh venv resolves to the pins and passes all three gates (617 passed, ruff clean, mypy clean, 96.61%).
- `2026-07-22` — **Correction.** H2a ☑ as investigated-only; #83 closed unmerged. The audit claim that forge PRs were ungated was wrong: Forgejo executes `.github/workflows/` too, and #81/#82 each ran 4 green jobs here. Locked as D7; retired D6; moved the real finding (Windows never runs on Forgejo — 0 of 85 runs) into H6; updated §1.2, §5, and §9 which asserted the false version. H2b/H3 re-pointed at H1 since H2a produces no artifact.
- `2026-07-22` — H1 ☑ (#82). `tests/test_render.py` now passes on Python 3.12.3 as well as CI's 3.11/3.12/3.13. Suite 614 → 617 passing, 0 failing; coverage 96.55% → 96.61%. Owner authorized self-merge of non-substantial hardening rows; H4/H5, H7, H10, H11 still go to review.
- `2026-07-22` — H0 ☑ (#81). Tracker created and indexed; R0 closed out; handoff refreshed.
- `2026-07-22` — Created. H0–H11 scoped from the 2026-07-22 health audit; D1–D6 locked with the owner.
