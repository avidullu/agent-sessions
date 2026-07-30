# Public Launch — agent-sessions + agent-session-router

> **Status:** `DONE / HISTORICAL` — public launch shipped and this tracker is
> **archived**. Both GitHub repos are **PUBLIC**, PyPI (`agent-session-hub` 0.2.0)
> and the VS Code Marketplace (`avidullu.agent-session-router` 0.1.0) are live,
> site at `https://agent-sessions.khelsutra.guru`. Residual polish split to forge
> issues **#136** (L16 demo) and **#137** (L17 baseline guide). **Owner:**
> `avidullu`. **Created:** `2026-07-23`. **Last updated:** `2026-07-30 10:53 IST`
> (final archive).
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived`
> **Tracking anchors:** §7 was the source of truth while active; fleet export
> remains `docs/PROJECT_TRACKER.md` (status hub slug `agent-sessions-launch`,
> frozen at 20/20 Complete). Indexed under `docs/archives/` in `docs/README.md`.
> **Relation to existing docs:** peer of `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md`
> (rules project continues); extends `docs/COMPOSE_STACK.md` and `docs/ROADMAP.md`.
> **Honesty note:** closeout verified 2026-07-30 (IST) against public GitHub, PyPI,
> Marketplace, site, local tests (761 hub / router coverage+smoke green), and
> `tools/check_pii.py` OK on the hub tree. Timestamps in this narrative use **IST**;
> the fleet table’s `Updated (UTC)` column stays ISO-8601 `…Z` (statuskit contract).

---

## 0. TL;DR

Ship both `agent-sessions` (Python hub) and `agent-session-router` (VS Code extension) as
**public, MIT-licensed, installable tools** so external users can discover, archive, and
search their AI coding sessions. The blockers are a missing license + private-flag + PII
in tracked files; the high-priority items are cross-platform install docs, PyPI/Marketplace
publishing, and a unified getting-started guide. This tracker covers 20 rows (L0–L19)
spanning 20 audit findings, plus FAQ publishing and WSL/Linux CI enforcement.

---

## 1. Problem & goal

### 1.1 What exists today

Both repos are functional and dogfooded daily:
- **agent-sessions**: 678 tests, 96.7% coverage, deterministic extractors for 5+ CLI agents, baseline pipeline (suggest → promote → publish), rules extraction (R1 shipped, R1b–R9 in progress).
- **agent-session-router**: 107 tests [verified on router `origin/master`], cross-platform CI, 8+ VS Code agent sources, pluggable discoverer/extractor architecture, router-index sidecar contract.

But they are **locked to a single user**:
- No open-source license (`license = {text = "Private"}`, router has `"private": true`).
- Tracked git files carry real user home-directory paths in `baseline/` and `archive/`.
- README is Windows/PowerShell-only; no `pip install` path; no Marketplace listing.
- No contributor guide, no changelog, no unified getting-started.

### 1.2 Goal

A new user on **any platform** (Windows, macOS, Linux, WSL) can:
1. Install the router from the VS Code Marketplace (or VSIX).
2. `pip install agent-session-hub` (or `git clone` + `pip install -e .`).
3. Follow a single `GETTING_STARTED.md` that covers both tools end-to-end.
4. Run `agent-archive export --all` and see their sessions in `archive/`.
5. Read a public FAQ, file issues, and submit PRs with clear contribution guidelines.

**Good looks like (achieved 2026-07-24; tracker closed 2026-07-30):**
- Both repos are MIT-licensed with sanitized public history (no personal session data).
- CI covers Windows + Linux (hub) and Windows + macOS + Linux (router); WSL path logic is unit-tested.
- `pip install agent-session-hub` works; `code --install-extension avidullu.agent-session-router` works.
- External users can discover the project, try it in < 5 minutes, and give feedback.

---

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|---|---|---|
| D1 | **Git history: clean-snapshot, not filter-branch.** The private Forgejo retains full history; the public GitHub repo starts from a sanitized HEAD. | Owner, 2026-07-23 [design] | Simpler, safer, and the private history has no value to external users. The Forgejo remains the canonical dev remote. |
| D2 | **License: MIT** for both repos (matching the router's existing LICENSE). | Owner, 2026-07-23 [design] | Permissive; consistent across the ecosystem. |
| D3 | **Package names stay as-is**: `agent-sessions` (PyPI) and `agent-session-router` (VS Code Marketplace). The naming inconsistency (plural vs. singular) is documented in the FAQ, not fixed by rename. | Owner, 2026-07-23 [design] | Avoids breaking the CLI entry point (`agent-archive`), the Python package namespace, and the VS Code extension ID. |
| D4 | **Publish targets**: PyPI for the hub, VS Code Marketplace + Open VSX for the router, GitHub Releases for both. | Owner, 2026-07-23 [design] | Maximum reach with minimum friction. |
| D5 | **CI must cover WSL + Linux**: the owner's `<dev-machine>` machine (Windows native + WSL) is the ratification environment. CI adds explicit WSL test lanes. | Owner request, 2026-07-23 [design] | Prevents Linux-only regressions; WSL path handling (e.g., `\\wsl.localhost\...`) is tested. |
| D6 | **FAQ is a tracked doc** (`docs/FAQ.md`) covering both repos; the router's inline FAQ moves there as the canonical source. | Owner request, 2026-07-23 [design] | Single source of truth; the router README links to it. |
| D7 | **One small PR per row** — same discipline as the rules project and hardening plan. | `AGENTS.md`, 2026-07-21 | Reviewable slices; no mega-PRs. |
| D8 | **Public repo is GitHub** (not Forgejo). The Forgejo remains the private dev remote; GitHub is the public face. The existing `github.com/avidullu/agent-sessions` mirror carries full pre-scrub history — L19 handles replacing it with a sanitized snapshot. After L19, mirroring continues (forge→github one-way) but `forge/main` stays the merge target for PRs. | Owner, 2026-07-23 [design] | GitHub is where external users will find us. The existing mirror's history must be replaced, not amended. |

---

## 3. Architecture / scope

### 3.1 Repo boundaries (unchanged from today)

```
agent-session-router (VS Code extension)          agent-sessions (Python CLI hub)
├── discovers VS Code agent sessions               ├── discovers CLI agent sessions
├── extracts messages                              ├── extracts messages
├── renders Markdown (contract v1)                 ├── renders Markdown + PDF (contract v1)
├── writes .router-index.jsonl sidecar             ├── merges sidecar → index.jsonl
└── auto-watch for new sessions                    └── baseline suggest → promote → publish
```

### 3.2 What changes for public users

| Today (private) | Target (public) |
|---|---|
| `git clone` + `pip install -e ".[dev]"` | `pip install agent-session-hub` |
| Clone + `npm ci` + `vsce package` | `code --install-extension avidullu.agent-session-router` (Marketplace) |
| Windows PowerShell README | Cross-platform README with bash + PowerShell |
| No FAQ | `docs/FAQ.md` as canonical FAQ |
| No CONTRIBUTING.md | `CONTRIBUTING.md` with setup, conventions, PR flow |
| Private paths in tracked files | Sanitized/anonymized everywhere (including `docs/`) |
| `license = {text = "Private"}` | MIT LICENSE file |
| Router `"private": true` | Removed |

---

## 4. Threat model / risk table

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PII leak via overlooked tracked file | Medium | High | L1 scrubs `baseline/`, `archive/`, `.claude-plugin/`, test fixtures; L11 adds a CI gate that fails on `C:\Users\` or `/home/` patterns in tracked JSON (allowlisted for `example-user` test fixtures); §9 DoD grep covers `docs/` too. |
| Broken install on fresh Linux/macOS | Medium | Medium | L3 rewrites README for cross-platform; L15 adds WSL + Linux CI lanes; `<dev-machine>` ratifies before merge. |
| Marketplace rejection | Low | High | L7 follows the `vsce publish` checklist; test with `vsce ls` first. |
| Confusion over hub vs. router naming | Medium | Low | L5 adds a prominent diagram + FAQ entry; D3 locks the names. |
| Router Prettier drift breaks first-contributor CI | High | Low | L8 lands a pure-formatting PR before any public announcement. |
| Redaction-v1 misses a credential pattern in a public contributor's session export | Low | High | L1 documents that redaction is best-effort; FAQ warns users to review exports before sharing. |

---

## 5. Honest limits — what this does NOT do

- **Does NOT host session data.** Both tools are local-first; no cloud storage, no telemetry, no network calls during export.
- **Does NOT guarantee perfect redaction.** Redaction-v1 catches high-confidence secrets (API keys, private keys, token patterns) and placeholders home-directory paths. Users must still review exported transcripts before sharing.
- **Does NOT provide search.** Search is delegated to `cass` per `docs/COMPOSE_STACK.md`.
- **Does NOT rewrite the router in Python or the hub in TypeScript.** The two repos stay in their respective languages; the OUTPUT_CONTRACT is the bridge.
- **Does NOT promise backward compatibility across major contract versions.** `format_version: 1` is stable; a future v2 will have a migration path but is not in scope here.

---

## 6. FAQ scope (L14)

The public FAQ (`docs/FAQ.md`) will cover:

1. What's the difference between agent-sessions and agent-session-router?
2. Does this upload my sessions anywhere? (No — local-first.)
3. Which AI coding agents are supported?
4. How do I install on Windows / macOS / Linux / WSL?
5. Where are my exported sessions saved?
6. How do I add support for a new AI agent? (Router pluggable architecture + hub extractor)
7. Can I use the router without the hub? (Yes — standalone Markdown.)
8. How do I update?
9. The watcher isn't working — what do I check?
10. How do I contribute? (Link to CONTRIBUTING.md)
11. What's redacted from exports and why?
12. Why "agent-sessions" (plural) vs "agent-session-router" (singular)?

---

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated. **One small PR per row.**

### 🔴 Blockers

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| L0 | **License**: add `LICENSE` (MIT) to agent-sessions, update `pyproject.toml` `license` field. Router already has MIT — verify it's correct. | — | No | ☑ | `384cb32` (direct to main) |
| L1 | **Privacy scrub (hub)**: remove/replace real user home-directory paths from `baseline/handoffs/index.jsonl`, `baseline/proposals/`, `baseline/projects/<user>/`, `baseline/candidates/*.predictions.json`, `.claude-plugin/marketplace.json`, `plugins/pr-review-loop/.claude-plugin/plugin.json`. Replace real usernames with `example-user`. (L0 is a sequencing choice, not a hard dependency — L1 can proceed in parallel.) Shipped as the **portable-path convention**: writers emit `~`-relative paths + username-free `source_origin`, indexes normalize on load, and all tracked catalogs were migrated — so the scrub cannot regress on the next export. | — | No | ☑ | #116 |
| L2 | **Privacy scrub + private flag (router)**: remove `"private": true` from `package.json`. Replace real usernames in test contract fixtures with `example-user`. Verify `.vscodeignore` excludes test fixtures from VSIX. | — | No | ☑ | router #25 |

### 🟠 High priority

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| L3 | **Cross-platform README overhaul (hub)**: rewrite Quick Start for bash + PowerShell; add `pip install` path; add macOS/Linux source examples; move agentic-install to a collapsible section. | L1 | No | ☑ | `65da2e7` (direct to main) |
| L4 | **PyPI packaging (hub)**: verify `pyproject.toml` metadata is complete (description, classifiers, keywords, URLs); add `twine` check to CI; publish first release to PyPI. Distribution name is **`agent-session-hub`** (`agent-sessions` was already taken on PyPI by an unrelated package). | L1 | No | ☑ | metadata + `release.yml` #120; **published** `agent-session-hub` 0.1.0 then 0.2.0 via OIDC Trusted Publishing on tag `v*` |
| L5 | **Unified GETTING_STARTED.md + naming clarity**: create `docs/GETTING_STARTED.md` covering both tools end-to-end (install → export → index → search). Add ecosystem diagram to both READMEs. Document the plural/singular naming in FAQ. | L3 | No | ☑ | `65da2e7`, `53732a8` |
| L6 | **Cross-platform `sources.example.toml`**: add macOS (`~/Library/Application Support/...`) and Linux (`~/.config/...`, `~/.local/share/...`) source examples alongside existing Windows/WSL examples. | L3 | No | ☑ | `65da2e7` |

### 🟡 Medium priority

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| L7 | **Marketplace publishing pipeline (router)**: add `vsce publish` + `ovsx publish` CI workflow on tag; document publisher token setup in `SETUP.md`; verify `publisher` field; remove `--allow-missing-repository` from install script. | L2 | No | ☑ | router `898f164` (publish itself fires on tag once the owner configures tokens) |
| L8 | **Prettier drift fix (router)**: run `npx prettier --write src/`; verify `npm run format:check` passes; pure-formatting PR (no logic changes). Resolved as an EOL pin, not a reformat: blobs were already prettier-clean/LF; Windows `autocrlf` checkouts materialized CRLF, so `format:check` failed only locally. `.gitattributes` now pins `src/**/*.ts eol=lf`. | L2 | No | ☑ | router #27 |
| L9 | **CONTRIBUTING.md for both repos**: setup instructions, `local_ci.sh` / `npm test` gates, how to add a new source extractor, PR conventions (one row per PR, review-before-merge), link to AGENTS.md. | L3, L5 | No | ☑ | `e2334c1` |
| L10 | **SESSION_HANDOFF private path cleanup**: replace real user paths in both repos' `SESSION_HANDOFF.md` with relative paths or `<repo-root>` placeholders. Widened to all tracked docs: tailnet hostnames and machine names placeholdered, `.mailmap` dropped. | L1 | No | ☑ | #115 (hub), router #25 |
| L11 | **CI gate against PII in tracked files**: add a CI step that fails on `C:\Users\` or `/home/` patterns in tracked JSON/JSONL (allowlisted for test fixtures with `example-user` placeholder). Covers `baseline/`, `archive/`, `agent_sessions/`, `tests/`, AND `docs/`. Shipped as `tools/check_pii.py` over **all** tracked files (home paths in native/WSL/encoded forms, tailnet hosts, personal emails). | L1 | No | ☑ | #117 |
| L12 | **CHANGELOG.md (hub)**: generate from git history + tracker changelogs; add to `pyproject.toml` `[project.urls]`; keep updated per release. | L4 | No | ☑ | `e2334c1` |
| L13 | **Router install script cleanup**: lead README with human instructions; move `agentic-install.sh` to a collapsible "For AI Agents" section; verify `--allow-missing-repository` is no longer needed after L7. | L7 | No | ☑ | router `898f164` |

### 🟢 Nice to have

| ID | Deliverable | Depends on | Gated? | Status | PR |
|----|-------------|-----------|--------|--------|----|
| L14 | **FAQ publishing**: create `docs/FAQ.md` covering the 12 questions in §6; link from both READMEs; the router's inline FAQ moves to the canonical doc. | L5 | No | ☑ | `e2334c1`, `8e06df2` |
| L15 | **WSL + Linux CI compatibility enforcement**: add WSL path-handling unit tests (e.g., `\\wsl.localhost\...` → POSIX conversion) that run on any Linux runner (no hosted WSL OS exists — the tests validate path logic, not kernel behaviour); ratify on `<dev-machine>` before merge. | L3 | No | ☑ | `tests/test_portable_paths.py` + WSL origin cases; hub CI matrix Ubuntu+Windows (3.11/3.13); router CI Ubuntu+Windows+macOS. Hub has no macOS CI lane (macOS still developer-unvalidated — see README honesty note). |
| L16 | **Demo / screenshots**: record a 30-second demo (install → export → see Markdown); add to both READMEs and the router's Marketplace listing. | L7 | No | ☑ | **Closed out of tracker** 2026-07-30 10:53 IST — filed forge issue **#136** (optional polish; not a launch blocker) |
| L17 | **Baseline user guide**: create `docs/BASELINE_USER_GUIDE.md` with concrete examples (what `baseline suggest` does, what a promotion looks like, when to calibrate). | L5 | No | ☑ | **Closed out of tracker** 2026-07-30 10:53 IST — filed forge issue **#137** (optional polish; not a launch blocker) |
| L18 | **Contract versioning doc**: add a § to `docs/OUTPUT_CONTRACT.md` on version compatibility and migration path (v1 → future v2). | — | No | ☑ | `docs/OUTPUT_CONTRACT.md` §9 Versioning & conformance (v1 goldens; v2 fixtures beside v1) |
| L19 | **GitHub mirror history replacement + public flip**: after L1+L2+L10+L11 scrub HEAD, replace the public mirrors with a sanitized snapshot and flip visibility to public. | L1, L11 | No (executed) | ☑ | executed 2026-07-24: histories archived to private `*-history-pre-launch` repos; forge reset to sanitized snapshots; mirrors force-synced; both GitHub repos **PUBLIC** (verified 2026-07-30). |
| L21 | **Personal dataset excision (owner decision, 2026-07-24)**: the public tree ships no owner data at all — removed `archive/index.jsonl` + `INDEX.md` (5,438-record personal catalog), `docs/DISCOVERY.md`, and all session-derived `baseline/` content (promoted project pages, global promotions, generated agent baselines, handoff index/audit, proposals, candidates, calibration results, prediction ledger, replay manifest). Structural docs, schemas, and `*.example.*` files stay. Demo data on the website may return as `example-user` content later. Residual prose mentions of project names in planning docs tracked as a follow-up issue. | L19 | No | ☑ | this PR |
| L20 | **Project landing page + hosting**: static `site/` page (motivation, rationale, architecture, quick start) served from the Cloudflare account (Workers static assets, same pattern as khelsutra.guru) or any static host; GitHub Pages intentionally skipped (Actions stay disabled on covered GitHub repos except the launch exemption). | L19 | No | ☑ | live at `https://agent-sessions.khelsutra.guru` + `https://agent-sessions-site.avi-dullu.workers.dev` (Worker `agent-sessions-site`, deployed 2026-07-24) |

---

## 8. Open questions — resolved at closeout

| Q | Resolution |
|---|---|
| Q1 D1 clean-snapshot vs filter-branch | **Clean-snapshot** (executed L19). |
| Q2 D3 keep names | **Kept** repo/extension names; PyPI uses `agent-session-hub` (see Q3). |
| Q3 PyPI name | **`agent-session-hub`** — `agent-sessions` was taken by an unrelated package. |
| Q4 Open VSX | **Optional** — workflow supports it; `OVSX_PAT` unset → skipped cleanly. Still open if owner wants VSCodium reach. |
| Q5 ratification scope | Platform-sensitive rows only (as assumed). |
| Q6 L19 plan | **Executed 2026-07-24** including public visibility flip. GitHub Actions **enabled** for both public repos (owner exemption). |

---

## 9. Definition of done

- [x] `pip install agent-session-hub` succeeds (verified 0.2.0; package name is not `agent-sessions`).
- [x] `code --install-extension avidullu.agent-session-router` succeeds from Marketplace.
- [x] `agent-archive export --all` produces archive catalog + Markdown without errors (dogfooded).
- [x] PII gate clean on hub tracked tree (`tools/check_pii.py` OK, 2026-07-30).
- [x] Router fixtures scrubbed; no `"private": true`.
- [x] L19 complete: sanitized public history lineage + both repos **PUBLIC**.
- [x] Both repos have MIT LICENSE files.
- [x] `docs/FAQ.md` exists and is linked from both READMEs.
- [x] `docs/GETTING_STARTED.md` exists and covers the full workflow.
- [x] `CONTRIBUTING.md` exists in the hub repo (router CONTRIBUTING added at closeout).
- [x] `CHANGELOG.md` exists in the hub repo.
- [x] CI green on hub (Windows + Linux) and router (Windows + macOS + Linux), with WSL path-handling unit tests (L15).
- [x] L16/L17 removed from active tracker scope — filed as forge **#136** / **#137** (optional polish).
- [ ] At least one external user has tried the tools and given feedback. *(adoption metric — not a ship gate; not tracked here)*

---

## 10. References

**Internal:**
- `docs/COMPOSE_STACK.md` — ecosystem ownership boundaries
- `docs/ROADMAP.md` — future features
- `docs/OUTPUT_CONTRACT.md` — format contract v1 (+ §9 versioning)
- `docs/PROJECT_DOC_TEMPLATE.md` — this tracker's template
- `docs/PROJECT_TRACKER.md` — fleet-exportable status table (frozen 20/20)
- `docs/FAQ.md`
- `docs/GETTING_STARTED.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`

**External:**
- Hub: `https://github.com/avidullu/agent-sessions` (public)
- Router: `https://github.com/avidullu/agent-session-router` (public)
- PyPI: `https://pypi.org/project/agent-session-hub/`
- Marketplace: `https://marketplace.visualstudio.com/items?itemName=avidullu.agent-session-router`
- Site: `https://agent-sessions.khelsutra.guru`
- Open VSX: `https://open-vsx.org/` (optional; not published yet)

### Post-launch follow-ups (tracker closed — work lives in issues)

- **#136** — L16 demo / screenshots (optional polish)
- **#137** — L17 baseline user guide (optional polish)
- Security: forge issue/PR **#133** — tracked-tree credential gate
- Privacy residual: issue **#122** — prose mentions of personal project names
- Optional later: Open VSX publish, hub macOS CI lane
- Product track: rules project resumes at **R2a** (see `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md`)

### Changelog
- `2026-07-30 10:53 IST` — **FINAL ARCHIVE.** Moved this file to `docs/archives/`. L16 → forge **#136**, L17 → forge **#137**; all §7 rows ☑. Fleet table frozen at **20/20 Complete**. Status hub slug `agent-sessions-launch` remains as a historical dashboard.
- `2026-07-30 ~10:20 IST` — **CLOSEOUT.** Tracker → `DONE`. Reconciled §7 + `docs/PROJECT_TRACKER.md` with live product (public repos, PyPI, Marketplace, site). L4/L15/L18/L19 marked ☑; L16/L17 still open polish at that moment. Fixed FAQ/GETTING_STARTED install footguns.
- `2026-07-24` (later) — **L19 executed to the flip gate; launch infrastructure live.** Owner approved Q6 and GitHub Actions for both repos (exemption recorded in `ops/forgejo-github-backup/policy.yaml`). Histories archived to private `*-history-pre-launch` forge repos; forge branches reset to sanitized single-commit snapshots; mirrors force-synced and fresh-clone verified. GitHub: Actions + Dependabot alerts/security fixes enabled (secret scanning auto-on at flip); CI (incl. `windows-latest` legs) running on mirrored pushes. Hub #120: `release.yml` (PyPI Trusted Publishing), `dependabot.yml`, `.gitleaks.toml`; router #27/#28: EOL pin + dependabot. Landing page deployed to Cloudflare (L20 ☑). Windows Forgejo runner made durable via scheduled task (issue #113, Option B). Remaining: owner manual scan → visibility flip → tag `v0.1.0` releases.
- `2026-07-23` — **Tracker created.** 20 audit findings organized into 20 rows (L0–L19; L19 added post-review for the GitHub mirror history replacement gating the public switch). D1–D8 decisions locked. FAQ scope (§6), WSL/Linux CI (L15), and cross-platform ratification plan included per owner request.
- `2026-07-23` — **Post-review amendments (PR #105 review):** P2 addressed (tracker prose uses placeholders instead of real usernames; `docs/` added to §9 DoD grep). P3 fixed (row count reconciled; **20 rows, L0–L19**, once P4's L19 is counted). P4 addressed (L19 added for GitHub mirror history replacement). Nits: 677→678, L15 WSL-lane clarified, L0→L1 noted as sequencing not dependency, router claims tagged as cross-repo-audit sourced. Link-checker CI (`tools/check_md_links.py` from `badminton-highlight-indexer`) added to `local_ci.sh` and `.github/workflows/ci.yml`.
- `2026-07-24` — **Blockers + privacy gates shipped; tracker reconciled with reality.** Pre-push hook CRLF fix (#114) un-reddened main on native Windows. L10 (#115): private-infra scrub of tracked docs, `.mailmap` dropped. L1 (#116): portable home-relative catalog paths — writers emit `~` forms + username-free `source_origin`, indexes normalize on load, all tracked catalogs migrated, contract fixtures re-aligned byte-identical with the router's (post router #25) copies. L11 (#117): `tools/check_pii.py` CI + local_ci gate (validated: 9,831 findings on the pre-L1 tree, zero after). Recorded the 2026-07-23/24 direct-to-main shipments for L0/L3/L5/L6/L9/L12/L14 (`384cb32`, `65da2e7`, `e2334c1`, `8e06df2`, `53732a8`) and router rows L2/L7/L13 (router #25, `898f164`). L19 marked owner-gated with an execution plan (Q6); L20 (landing page + Cloudflare hosting) added. Local checkouts migrated to Forgejo-primary remotes per `ops/forgejo-github-backup` policy. Known drift filed: the router vendors a `deepseek_empty_transcript` contract fixture the hub does not.
- `2026-07-23` — **Merged onto post-R1b main (#104).** Resolved the `SESSION_HANDOFF.md` conflict (kept main's R1b-current rules next-steps; re-applied the launch-track additions). Reconciled the residual count references left over from P3+P4 (18/19 → **20 rows, L0–L19**) here and in the handoff. Verified P2/P4 fixes and the new link-check gate against the merged tree via `local_ci.sh`.
