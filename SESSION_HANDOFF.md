# Session Handoff

Updated: 2026-07-24 (🚀 LAUNCHED — both repos public, PyPI + VS Code Marketplace live, site on custom domain)

## You Are Here

**🚀 PUBLIC LAUNCH IS COMPLETE.** All channels are live and verified:
- **GitHub:** [agent-sessions](https://github.com/avidullu/agent-sessions) +
  [agent-session-router](https://github.com/avidullu/agent-session-router) —
  PUBLIC, MIT, CI green, secret scanning + push protection on.
- **PyPI:** [`agent-session-hub` 0.2.0](https://pypi.org/project/agent-session-hub/)
  — verified: `pip install agent-session-hub` → `agent-archive` runs.
- **VS Code Marketplace:** [`avidullu.agent-session-router`](https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router)
  — `code --install-extension avidullu.agent-session-router`.
- **Site:** https://agent-sessions.khelsutra.guru (Cloudflare Worker, custom domain).
- **Flyer:** `Agentic-Coding/agent-sessions-flyer.pdf` + `.png` (QR → site).

Both release pipelines are wired for future versions: bump the version and tag
`v*` on the **forge** (never GitHub) → mirror → `release.yml` (PyPI, OIDC
trusted publishing, no token) / `publish.yml` (Marketplace, `VSCE_PAT` secret).

**Tiny cosmetic leftovers (non-blocking):** (1) enable GitHub CodeQL default
setup in Settings → Code security (the CLI token lacks `security_events`);
(2) the Marketplace listing shows the pre-publish README until the next version
tag refreshes it. Housekeeping: rotate the `DIGITALOCEAN_ACCESS_TOKEN` in the
Windows user env; move `PyPI-Recovery-Codes-*.txt` out of `Agentic-Coding/`.

**Foundation Hardening is DONE** — H0–H11 all merged. Rules project (R2a
onward) is unblocked and parked at the owner's request; **now clear to resume
post-launch** (see below).

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

## LAUNCH — done. Notes for future releases & operations

- **Cutting a new release:** bump `version` in `pyproject.toml` (hub) or
  `package.json` (router), commit via a forge PR, then
  `git tag -a vX.Y.Z <sha> && git push origin vX.Y.Z` on the **forge** and
  trigger a mirror sync. The tag reaches GitHub and the release pipeline fires.
  Never tag on GitHub; never merge on GitHub — the mirror overwrites it.
- **PyPI** uses OIDC trusted publishing (pending-publisher registered for
  `agent-session-hub` / repo `agent-sessions` / `release.yml` / env `pypi`) —
  no token. If a publish fails on a Sigstore/Rekor 5xx (attestation step), it's
  transient: `gh run rerun <id> --failed` (that's what happened for 0.2.0).
- **Marketplace** uses the `VSCE_PAT` repo secret; Open VSX is optional
  (`OVSX_PAT`, currently unset → skipped cleanly).
- **Forge write API flakiness:** the tailnet HTTPS ingress intermittently drops
  POST/PATCH (GETs fine). Workaround used all session: run writes from the forge
  host, `ssh avidullu@avis-pbook … curl http://127.0.0.1:3000/api/v1/…`.
- **CI gotcha (fixed):** `secrets` context is invalid in a step `if:` — map to
  job `env` first (this bit the publish workflow; see router `publish.yml`).
- **Windows self-hosted runner:** see `avis-agents-xdsync/ops/forgejo-runner-fleet/WINDOWS-RUNNER.md`.

## Next up (post-launch, owner's call)

Rules project resumes at **R2a — role-privileged scoring** (precision-hardening,
D23). See the rules section below. Also worth a small PR: document the
"merge on Forgejo, mirror to GitHub" convention in CONTRIBUTING (owner idea).

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
