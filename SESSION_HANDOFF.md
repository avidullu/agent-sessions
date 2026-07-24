# Session Handoff

Updated: 2026-07-24 (launch sprint 2 — L19 executed, dataset excised, Windows CI green, site on custom domain; the public flip + two token setups are the only things left, all owner-only)

## You Are Here

**PUBLIC LAUNCH IS ONE FLIP AWAY.** Everything the owner delegated is done;
what remains is intentionally owner-only. See the "LAUNCH — what's left for the
owner" section below FIRST if resuming to finish the launch.

**Foundation Hardening is DONE** — H0–H11 all merged. Rules project (R2a
onward) is unblocked and parked at the owner's request until after launch.

**Public launch — where it actually stands (2026-07-24, end of sprint 2):**
- GitHub `avidullu/agent-sessions` and `avidullu/agent-session-router` are
  **sanitized single-commit snapshots, still PRIVATE**. Full pre-launch history
  is preserved on the private forge as `*-history-pre-launch` repos. (L19 done.)
- **The public tree ships ZERO owner data** (L21, #123 + re-snapshot): removed
  `archive/index.jsonl`/`INDEX.md` (5,438 records), `docs/DISCOVERY.md`, and all
  session-derived `baseline/` content. Only structural docs/schemas/`*.example.*`
  remain. Residual project-name prose mentions tracked in issue #122 (owner
  accepted the "someone digs history" risk).
- **Privacy is CI-enforced**: `tools/check_pii.py` gate fails on any real home
  path / tailnet host / personal email in tracked files. Portable `~` catalog
  paths (#116) mean the scrub can't regress on future exports.
- **GitHub Actions ON** for both (owner-approved exemption in
  `avis-agents-xdsync/ops/forgejo-github-backup/policy.yaml`); Dependabot alerts +
  security fixes on; CI (incl. `windows-latest`) green on both forges.
- **Windows CI fully fixed & hardened** — see the Windows runner section below.
- **CI matrix trimmed** to boundary Pythons 3.11 + 3.13 (#125); 6→4 test legs.
- **Landing page LIVE**: https://agent-sessions.khelsutra.guru (Cloudflare Worker
  `agent-sessions-site`, custom domain on the khelsutra.guru zone) + the
  `*.workers.dev` URL. (L20 done.)
- **Release pipelines in place**: hub `release.yml` = PyPI Trusted Publishing on
  tag `v*` (OIDC, no stored token); router `publish.yml` = Marketplace on tag,
  `VSCE_PAT` secret **already set** (2026-07-24), Open VSX now optional (#29).
- Local checkouts are Forgejo-primary (origin=forge, github=backup, never push
  to github). All work this session went forge→PR→merge→mirror.

## LAUNCH — what's left for the owner (do in this order)

1. **Manual PII scan** of the two private GitHub repos (they're one commit each;
   focus on `baseline/*/README.md` structure, `*.example.*`, docs prose).
2. **PyPI pending publisher** (2 min, no token): pypi.org → your account →
   Publishing → add pending publisher: project `agent-sessions`, owner
   `avidullu`, repo `agent-sessions`, workflow `release.yml`, environment `pypi`.
3. **Marketplace publisher** `avidullu` — **verified to exist** (2026-07-24) and
   matches `package.json`. Nothing to do unless you deleted it.
4. **Flip both GitHub repos to Public** (Settings → Danger Zone), or ask the
   next session to flip via `gh`/API.
5. **After the flip**, the next session should: enable GitHub secret scanning +
   push protection + CodeQL default setup (API), then **tag `v0.1.0`** on the
   forge for both repos — the mirror carries the tag to GitHub and the release
   pipelines fire (PyPI + Marketplace; Open VSX skipped unless `OVSX_PAT` set).
   DO NOT tag before the flip (publishing would leak the code pre-public).

**Known flags:** a `DIGITALOCEAN_ACCESS_TOKEN` in the owner's Windows user env is
inherited by CI jobs on the self-hosted runner — rotate/relocate it. The
tailnet HTTPS ingress to the forge intermittently drops POST/PATCH (GETs fine);
workaround is to run write API calls from the forge host via
`ssh avidullu@avis-pbook … curl http://127.0.0.1:3000/api/v1/…`.

## Windows CI runner — fixed, hardened, documented

Native Windows forgejo-runner on AVIS-MSI now runs the `windows-latest` legs
green (761 passed × 3 in the final probe). **Full runbook + invariants:
`avis-agents-xdsync/ops/forgejo-runner-fleet/WINDOWS-RUNNER.md`** (read before
touching it). The six root causes fixed: fragile task wrapper + Task Scheduler
races (→ cmd relaunch-loop supervisor + 30-min watchdog task), PATH missing
Git/PowerShell, missing tool cache, setup-python admin requirement (→ pre-seeded
CPython 3.11/3.12/3.13 tool cache), a **credential-ghost WSL runner** stealing
every windows job (→ repointed to its own registration, duplicate deleted,
backups scrubbed), and the System32 WSL bash shim shadowing Git bash. The WSL
overflow runner is currently **stopped** (fix required killing it; `sudo
systemctl start forgejo-runner` in WSL to revive).

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

Note: L21 removed `docs/EFFICACY_CHECK_2026-07-23.md`'s companion data files but
the doc itself and `tools/rules_demo.py` remain; if rules work resumes, the
efficacy harness now runs against locally-generated data, not tracked fixtures.

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

**Public launch — see the "LAUNCH — what's left for the owner" section above.**
The launch is not a parallel track anymore; it's the near-complete main thread,
blocked only on owner-only steps (scan → flip → tags). Full 21-row detail in
`docs/PUBLIC_LAUNCH_TRACKER.md` §7 (reconciled 2026-07-24, changelog current).

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
