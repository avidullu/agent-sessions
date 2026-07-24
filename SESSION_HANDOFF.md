# Session Handoff

Updated: 2026-07-24 (launch sprint — blockers L0–L2 and privacy gates L10/L11 shipped; L19 + public flip await owner go-ahead)

## You Are Here

**Foundation Hardening is DONE** — H0–H11 all merged (#81–#96/#98; tracker:
`docs/FOUNDATION_HARDENING_PLAN.md`, kept in `docs/` per its §9 until R1 starts).
The gate on the rules project is open.

**Public launch is IN PROGRESS and far along** — see
`docs/PUBLIC_LAUNCH_TRACKER.md` §7 (reconciled 2026-07-24). Shipped: L0–L3,
L5–L7, L9–L14 (licenses, both privacy scrubs, portable `~` catalog paths
with on-load normalization + migration (#116), the `tools/check_pii.py` CI
gate (#117), docs/packaging rows, marketplace workflow). Remaining:
L4-publish (PyPI token), L8 (unverified), L15–L18 (nice-to-haves), **L19 +
the GitHub public flip — owner-gated, execution plan in tracker Q6**, and
L20 (landing page drafted; Cloudflare hookup pending). Local checkouts now
use Forgejo-primary remotes (origin=forge, github=backup). This runs in
parallel with the rules project: the rules rows (R2a onward) continue
unblocked.

The 2026-07-22 repo review's course corrections (issue #99, file:line
evidence) are **locked into the rules tracker as D16–D22**: pull-model
pipeline (extract → propose → curate → compile → eval), export-time
extraction into a tracked redacted evidence ledger, echo-contamination
controls with the ≥80% saturation rule, polarity+topic clustering with
contradiction pairs as an output, template-as-canon tracker conformance
(amends D2), adapter context budgets, and in-repo master snapshots. Rows
R1a (spike), R1b (ledger), R11 (scorecard) added; the project is
**IN PROGRESS** — R1a ☑ (#102), **D1 confirmed** by owner LGTM on issue #99
(2026-07-23), R1 extractor (#103), R1b evidence ledger (#104), and R2 clusterer
(#107) shipped. A 2026-07-23 mid-project **efficacy run** on 1,125 real sessions
(8/10 recall; 43 secrets quarantined) found the ranking scores agent boilerplate
over user preferences — reprioritizing precision-hardening **R2a–R2c ahead of R3**
(D23). Baseline frozen in `docs/EFFICACY_CHECK_2026-07-23.md`; harness
`tools/rules_demo.py`; private artifact holds the illustrative side-by-side.

## Next Steps / Open Threads

**Rules project (continuing) — precision-hardening first (D23):**
1. **R2a — role-privileged scoring** (`rule_clusterer`): weight user-authored
   evidence far above system/developer/request-prompt/assistant roles — the
   efficacy check's #1 lever, proven to surface genuine preferences. Then
   **R2b** (D18 saturation as a score penalty) and **R2c** (extraction code/log
   filtering). Re-run `tools/rules_demo.py` after each and compare
   `docs/EFFICACY_CHECK_2026-07-23.md` §2 to quantify the gain.
2. Then **R3 — classifier** (`rule_classifier.py`: scope + prediction-ID linker
   + `auto|assisted|manual` detectability, D10) on the cleaned clusters, then R4
   (master schema + compiler, moves `AGENT_TARGETS` + E5, D16) per §7.
3. Backlog unchanged: issues #32, #19; follow-ups #92 (aggressive ratchet),
   #93 (history purge + catalog redaction), #94 (extractor de-dup),
   #95 (complexity refactor).

**Public launch (parallel track):**
4. **L19 + public flip — owner decision:** approve (or amend) the execution
   plan in tracker Q6, then run it. This is the gate on everything public.
5. **Releases:** configure PyPI + Marketplace/Open VSX tokens, then publish
   (L4/L7 pipelines are in place).
6. **L20 — landing page:** land `site/`, connect Cloudflare (Workers Builds
   or one `npx wrangler login` + deploy).
7. See `docs/PUBLIC_LAUNCH_TRACKER.md` §7 for the full 21-row breakdown.

## Ramp-Up Kit

- `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md` — the active tracked project (rules)
- `docs/EFFICACY_CHECK_2026-07-23.md` — mid-project efficacy baseline (metrics to beat)
- `tools/rules_demo.py` — reproducible efficacy harness (real modules, real sessions)
- `docs/PUBLIC_LAUNCH_TRACKER.md` — public launch tracker (L0–L19, active in parallel)
- issue #99 — 2026-07-22 review findings (evidence with file:line)
- `docs/FOUNDATION_HARDENING_PLAN.md` — DONE; §7 shows what the foundation
  now guarantees
- `AGENTS.md` — PR → review → LGTM → merge discipline; run
  `./scripts/local_ci.sh` before every push
- `agent_sessions/baseline_predictions.py`, `baseline_publish.py`,
  `baseline_redaction.py`, `render.py` — the code the R rows reuse
- Router repo (feeder): `../agent-session-router` (cloned beside this repo)

## Key Decisions

- **Foundation before features** — satisfied 2026-07-22; H0–H11 merged.
- **PRs are opened and merged on Forgejo** (the private forge); GitHub is the
  mirror. Verify `forge/main == origin/main` before branching; branch from
  `forge/main`. (Mirror fast-forwarded 2026-07-22 after lagging 12 commits.)
- **Propose-only (D7) / pull model (D8)** govern all rules-project writes;
  merges require owner approval scoped to the PR or project.
- Rendered archive Markdown/PDF transcript bodies remain local-only by
  default; `archive/index.jsonl` and `archive/INDEX.md` are the portable
  tracked catalog.
- Hub and router catalog identity keeps distinct same-session-id records
  apart by including `sha256`; reuse checks use tail hashes.
