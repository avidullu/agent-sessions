# Public Launch — agent-sessions + agent-session-router

> **Status:** `IN PROGRESS` — blockers (L0–L2) and privacy gates (L10, L11) are shipped; docs/packaging rows L3–L14 largely shipped; **L19 (mirror history replacement) + the public visibility flip await explicit owner go-ahead**, as do the PyPI/Marketplace publishes (owner tokens). **Owner:** `avidullu`. **Created:** `2026-07-23`. **Last updated:** `2026-07-24`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived`
> **Tracking anchors:** §7 progress tracker is the source of truth; indexed in `docs/README.md`; pointer in `SESSION_HANDOFF.md`.
> **Relation to existing docs:** peer of `docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md` (rules project continues in parallel); extends `docs/COMPOSE_STACK.md` (ecosystem scope) and `docs/ROADMAP.md` (future features); the `agent-session-router` companion repo is tracked inline (rows tagged `[router]`).
> **Honesty note:** claims marked `[verified]` were checked against `forge/main` at `88b2224` (agent-sessions) and `origin/master` at `4a0fa62` (router) on 2026-07-23; `[design]` items are scoped but not implemented; `[researched]` items draw from the 2026-07-23 cross-repo audit.

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
2. `pip install agent-sessions` (or `git clone` + `pip install -e .`).
3. Follow a single `GETTING_STARTED.md` that covers both tools end-to-end.
4. Run `agent-archive export --all` and see their sessions in `archive/`.
5. Read a public FAQ, file issues, and submit PRs with clear contribution guidelines.

**Good looks like:**
- Both repos are MIT-licensed with clean git history (no PII).
- CI enforces WSL + Linux + macOS + Windows — user's `<dev-machine>` machine ratifies WSL/Linux behaviour.
- `pip install agent-sessions` works; `code --install-extension agent-session-router` works.
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
| `git clone` + `pip install -e ".[dev]"` | `pip install agent-sessions` |
| Clone + `npm ci` + `vsce package` | `code --install-extension agent-session-router` (Marketplace) |
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
| L4 | **PyPI packaging (hub)**: verify `pyproject.toml` metadata is complete (description, classifiers, keywords, URLs); add `twine` check to CI; publish first release to PyPI as `agent-sessions`. | L1 | No | ◐ | metadata `384cb32`; `release.yml` (build + twine check + Trusted Publishing) landed #120 — publish fires on tag `v*` once the owner adds the PyPI pending publisher (repo `avidullu/agent-sessions`, workflow `release.yml`, environment `pypi`) |
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
| L15 | **WSL + Linux CI compatibility enforcement**: add WSL path-handling unit tests (e.g., `\\wsl.localhost\...` → POSIX conversion) that run on any Linux runner (no hosted WSL OS exists — the tests validate path logic, not kernel behaviour); ratify on `<dev-machine>` before merge. | L3 | No | ☐ | — |
| L16 | **Demo / screenshots**: record a 30-second demo (install → export → see Markdown); add to both READMEs and the router's Marketplace listing. | L7 | No | ☐ | — |
| L17 | **Baseline user guide**: create `docs/BASELINE_USER_GUIDE.md` with concrete examples (what `baseline suggest` does, what a promotion looks like, when to calibrate). | L5 | No | ☐ | — |
| L18 | **Contract versioning doc**: add a § to `docs/OUTPUT_CONTRACT.md` on version compatibility and migration path (v1 → future v2). | — | No | ☐ | — |
| L19 | **GitHub mirror history replacement**: after L1+L2+L10+L11 scrub HEAD, replace the `github.com/avidullu/agent-sessions` mirror with a sanitized snapshot (force-push or delete+recreate). The existing mirror carries full pre-scrub PII in its commit history; a HEAD-only scrub leaves PII one `git log` away. This row gates the "public" switch. | L1, L11 | **Yes — owner go-ahead** | ◐ | **executed 2026-07-24** per Q6 (owner-approved): full histories archived to private `*-history-pre-launch` repos (14 + 4 branches), forge `main`/`master` reset to sanitized single-commit snapshots, mirrors force-synced — GitHub now carries exactly one branch/one commit per repo, fresh-clone verified (check_pii OK; gitleaks: only the allowlisted synthetic test secrets). **Remaining: owner's manual scan + the private→public flip.** |
| L21 | **Personal dataset excision (owner decision, 2026-07-24)**: the public tree ships no owner data at all — removed `archive/index.jsonl` + `INDEX.md` (5,438-record personal catalog), `docs/DISCOVERY.md`, and all session-derived `baseline/` content (promoted project pages, global promotions, generated agent baselines, handoff index/audit, proposals, candidates, calibration results, prediction ledger, replay manifest). Structural docs, schemas, and `*.example.*` files stay. Demo data on the website may return as `example-user` content later. Residual prose mentions of project names in planning docs tracked as a follow-up issue. | L19 | No | ☑ | this PR |
| L20 | **Project landing page + hosting**: static `site/` page (motivation, rationale, architecture, quick start) served from the Cloudflare account (Workers static assets, same pattern as khelsutra.guru) or any static host; GitHub Pages intentionally skipped (Actions stay disabled on covered GitHub repos except the launch exemption). | L19 | No | ☑ | live at `https://agent-sessions-site.avi-dullu.workers.dev` (Worker `agent-sessions-site`, deployed 2026-07-24) |

---

## 8. Open questions

- **Q1 (owner):** Confirm D1 — clean-snapshot or filter-branch for git history? The tracker assumes clean-snapshot (simpler, safer). If filter-branch is preferred, L1 scope expands significantly.
- **Q2 (owner):** Confirm D3 — keep `agent-sessions` / `agent-session-router` naming as-is? Renaming is possible but affects PyPI package, VS Code extension ID, and all cross-references.
- **Q3 (owner):** PyPI package name: `agent-sessions` or `agent-session-hub`? The former matches the repo; the latter distinguishes from the router. The tracker assumes `agent-sessions`.
- **Q4 (external):** Should `agent-session-router` also publish to Open VSX (open-vsx.org) for VSCodium users? D4 includes it tentatively — owner to confirm.
- **Q5 (owner):** Should `<dev-machine>` ratify every L-row PR, or only the CI/lint ones (L8, L11, L15)? The tracker assumes ratification only for platform-sensitive rows.
- **Q6 (owner, gating — L19 execution plan, proposed 2026-07-24):** (1) create an orphan "sanitized snapshot" root commit from the current `forge/main` tree; (2) preserve the full private history on the private forge as branch `private-history-pre-launch`; (3) reset forge `main` to the snapshot lineage; (4) delete + recreate the GitHub mirror repo (or force-sync) so GitHub carries only the sanitized snapshot; (5) re-verify the forge→GitHub push mirror; (6) flip both GitHub repos to public. Steps 3–6 are effectively irreversible and run **only on explicit owner instruction**. Related decision needed: GitHub Actions stay disabled on covered repos per backup policy — external contributors would get no CI on GitHub PRs. Options: keep Forgejo as the sole CI+merge target and say so in CONTRIBUTING, or explicitly exempt these two public repos from the Actions-disabled rule.

---

## 9. Definition of done

- [ ] `pip install agent-sessions` succeeds on a clean Windows, macOS, and Linux machine.
- [ ] `code --install-extension agent-session-router` succeeds from Marketplace (or Open VSX).
- [ ] `agent-archive export --all` produces `archive/index.jsonl` + Markdown without errors.
- [ ] PII grep across `baseline/ archive/ agent_sessions/ tests/ docs/` returns zero results for real user paths (allowlisted: test fixtures with `example-user` placeholder).
- [ ] PII grep across `agent-session-router/src/ agent-session-router/test/` returns zero results (allowlisted: fixtures with `example-user` placeholder).
- [ ] L19 complete: GitHub mirror history is the sanitized snapshot, not the full Forgejo history.
- [ ] Both repos have MIT LICENSE files.
- [ ] Router `package.json` has no `"private": true`.
- [ ] `docs/FAQ.md` exists and is linked from both READMEs.
- [ ] `docs/GETTING_STARTED.md` exists and covers the full workflow.
- [ ] `CONTRIBUTING.md` exists in both repos.
- [ ] `CHANGELOG.md` exists in the hub repo.
- [ ] CI is green on Windows, macOS, Linux (hub), and Windows, macOS, Linux (router) — including WSL path-handling tests (L15).
- [ ] At least one external user has tried the tools and given feedback.

---

## 10. References

**Internal:**
- `docs/COMPOSE_STACK.md` — ecosystem ownership boundaries
- `docs/ROADMAP.md` — future features
- `docs/OUTPUT_CONTRACT.md` — format contract v1
- `docs/PROJECT_DOC_TEMPLATE.md` — this tracker's template
- `docs/FAQ.md` — (to be created, L14)
- `docs/GETTING_STARTED.md` — (to be created, L5)
- `CONTRIBUTING.md` — (to be created, L9)
- `CHANGELOG.md` — (to be created, L12)

**External:**
- Router repo: `https://github.com/avidullu/agent-session-router` (public mirror)
- VS Code Marketplace: `https://marketplace.visualstudio.com/`
- PyPI: `https://pypi.org/project/agent-sessions/`
- Open VSX: `https://open-vsx.org/`

### Changelog
- `2026-07-24` (later) — **L19 executed to the flip gate; launch infrastructure live.** Owner approved Q6 and GitHub Actions for both repos (exemption recorded in `ops/forgejo-github-backup/policy.yaml`). Histories archived to private `*-history-pre-launch` forge repos; forge branches reset to sanitized single-commit snapshots; mirrors force-synced and fresh-clone verified. GitHub: Actions + Dependabot alerts/security fixes enabled (secret scanning auto-on at flip); CI (incl. `windows-latest` legs) running on mirrored pushes. Hub #120: `release.yml` (PyPI Trusted Publishing), `dependabot.yml`, `.gitleaks.toml`; router #27/#28: EOL pin + dependabot. Landing page deployed to Cloudflare (L20 ☑). Windows Forgejo runner made durable via scheduled task (issue #113, Option B). Remaining: owner manual scan → visibility flip → tag `v0.1.0` releases.
- `2026-07-23` — **Tracker created.** 20 audit findings organized into 20 rows (L0–L19; L19 added post-review for the GitHub mirror history replacement gating the public switch). D1–D8 decisions locked. FAQ scope (§6), WSL/Linux CI (L15), and cross-platform ratification plan included per owner request.
- `2026-07-23` — **Post-review amendments (PR #105 review):** P2 addressed (tracker prose uses placeholders instead of real usernames; `docs/` added to §9 DoD grep). P3 fixed (row count reconciled; **20 rows, L0–L19**, once P4's L19 is counted). P4 addressed (L19 added for GitHub mirror history replacement). Nits: 677→678, L15 WSL-lane clarified, L0→L1 noted as sequencing not dependency, router claims tagged as cross-repo-audit sourced. Link-checker CI (`tools/check_md_links.py` from `badminton-highlight-indexer`) added to `local_ci.sh` and `.github/workflows/ci.yml`.
- `2026-07-24` — **Blockers + privacy gates shipped; tracker reconciled with reality.** Pre-push hook CRLF fix (#114) un-reddened main on native Windows. L10 (#115): private-infra scrub of tracked docs, `.mailmap` dropped. L1 (#116): portable home-relative catalog paths — writers emit `~` forms + username-free `source_origin`, indexes normalize on load, all tracked catalogs migrated, contract fixtures re-aligned byte-identical with the router's (post router #25) copies. L11 (#117): `tools/check_pii.py` CI + local_ci gate (validated: 9,831 findings on the pre-L1 tree, zero after). Recorded the 2026-07-23/24 direct-to-main shipments for L0/L3/L5/L6/L9/L12/L14 (`384cb32`, `65da2e7`, `e2334c1`, `8e06df2`, `53732a8`) and router rows L2/L7/L13 (router #25, `898f164`). L19 marked owner-gated with an execution plan (Q6); L20 (landing page + Cloudflare hosting) added. Local checkouts migrated to Forgejo-primary remotes per `ops/forgejo-github-backup` policy. Known drift filed: the router vendors a `deepseek_empty_transcript` contract fixture the hub does not.
- `2026-07-23` — **Merged onto post-R1b main (#104).** Resolved the `SESSION_HANDOFF.md` conflict (kept main's R1b-current rules next-steps; re-applied the launch-track additions). Reconciled the residual count references left over from P3+P4 (18/19 → **20 rows, L0–L19**) here and in the handoff. Verified P2/P4 fixes and the new link-check gate against the merged tree via `local_ci.sh`.
