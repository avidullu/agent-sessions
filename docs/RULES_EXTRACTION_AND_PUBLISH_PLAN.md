# Agentic Knowledge Extraction & Cross-Agent Publishing

> **Status:** `IN PROGRESS` — R0, R1a, R1, R1b, R2 ☑; **2026-07-23 mid-project efficacy run reprioritized precision-hardening (R2a–R2c) ahead of R3** (D23; baseline preserved in `docs/EFFICACY_CHECK_2026-07-23.md`); next: R2a. D1 confirmed 2026-07-23 on R1a evidence (owner LGTM, issue #99). Course corrections D16–D22 locked from the 2026-07-22 review (issue #99); foundation gates satisfied 2026-07-22 (`docs/FOUNDATION_HARDENING_PLAN.md` DONE, H0–H11 all merged). **Owner:** `avidullu`. **Created:** `2026-07-21`. **Last updated:** `2026-07-23`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived`
> **Tracking anchors:** §7 progress tracker is the source of truth; indexed in `docs/README.md`; pointer in `SESSION_HANDOFF.md`.
> **Relation to existing docs:** extends `docs/archives/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` (K0–K12 pipeline); composes with `docs/ENGINEERING_BASELINE.md` (promote/publish); **was gated by** `docs/FOUNDATION_HARDENING_PLAN.md` (foundation-first, D1; DONE 2026-07-22, gate cleared); feeds into agent instruction files (`AGENTS.md`, `CLAUDE.md`, `.instructions.md`, `SKILL.md`, `/memories/`).
> **Honesty note:** claims marked `[verified]` were checked against `origin/main` at `0addbc3`; claims marked `[verified 2026-07-22]` were measured during the 2026-07-22 repo review (issue #99) against `main` at `f3810f6`; `[design]` items are scoped but not implemented.

---

## 0. TL;DR

Mine archived coding-agent sessions for **concrete, imperative rules** ("always X",
"never Y", "must Z") — not just abstract guardrails — and publish them into the
**exact format each agent consumes** (CLAUDE.md, AGENTS.md, .instructions.md,
SKILL.md, memory).  Additionally, detect the user's preferred project-tracker
format (§7 deliverables table, status headers, decisions-locked sections) and
**enforce it across all sessions on all projects, irrespective of which agent
generated them**.  The user gets one consistent set of approved artifacts no
matter which agent they happen to be using.

---

## 1. Problem & goal

### 1.1  What exists today

The `baseline suggest → promote → publish` pipeline produces **abstract guardrails**
(PR-Only Repo Writes, Handoff & Resume, Tracked Project Docs).  These are useful
as principles but are not **concrete enough** for an agent to follow on first use.
Compare:

| Current tool output | What the user's memory already has |
|---|---|
| "Agents must not push directly to durable repos." | "Always `git checkout main`, `git pull`, then `git checkout -b <branch>`. Never commit directly to `main`." |
| "Agents should discover and run the repo's real test, lint, type, coverage gates." | "Wait for ALL 10 checks to go green: Ruff, Mypy, Full test suite, Golden x3, License scan. Mypy catches things `ruff` doesn't." |
| "Agents must not push directly to durable repos." | "**Never auto-merge PRs.** Wait for review comments or an explicit owner LGTM before merging. Merge only after CI is green AND explicit approval — even if the PR author and reviewer are the same GitHub account." |
| _(no output)_ | "isort groups: stdlib → third-party → first-party (`backend.`). `import pytest` is THIRD-PARTY, not stdlib." |

The user has already captured 6 concrete rules in `/memories/patterns.md` that the
tool never surfaced — they were manually curated from experience.

### 1.2  The tracker enforcement gap

The user has a **preferred project-tracker format** (status header, decisions-locked
table, §7 deliverable rows, one PR per row, DONE → archive).  This format is used
in `badminton-highlight-indexer`, `agent-sessions`, and other projects.  But:

- Different agents produce different structures for the same concept.
- No agent "knows" that `docs/archives/FIRST_USER_SETUP_TRACKER.md` and `docs/archives/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` are the same pattern.
- New projects start without a tracker, and agents improvise incompatible formats.
- The user must manually enforce consistency across agents.

**The tool should be the enforcement mechanism.**  It should identify the canonical
tracker format from the user's existing artifacts, detect when a new project is
missing one, and generate a scaffold in the correct format — irrespective of which
agent is active.

### 1.3  Goal

A single command (`baseline rules extract`) that:

1. **Mines** all archived sessions for concrete imperative rules.
2. **Clusters** duplicates across sessions, agents, and projects.
3. **Classifies** each rule as global, project-scoped, or repo-scoped.
4. **Publishes** each rule in the right format for each target agent.
5. **Detects** the user's preferred tracker format and enforces it across projects.

**Good looks like:**

1. After every archive export, `baseline rules extract` produces updated
   `CLAUDE.md` / `AGENTS.md` / `.instructions.md` snippets with concrete rules.
2. A new project that lacks a tracker gets a scaffold generated in the user's format.
3. Rules that appear in 10+ sessions across multiple agents are promoted as trusted.
4. Rules that contradict each other (one agent says "always squash", another says
   "always merge") are flagged for human resolution.
5. The user's `/memories/patterns.md` is kept in sync — new rules are proposed,
   stale ones flagged.

---

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|---|---|---|
| D1 | Rule extraction is **deterministic** (regex + clustering), not LLM-based. **Confirmed 2026-07-23** on R1a evidence — 6/6 session-derivable recall held after echo exclusion (owner LGTM, issue #99). | Owner preference, 2026-07-21; confirmed 2026-07-23 | Same stance as baseline predictions; avoids hallucination risk. |
| D2 | ~~The canonical tracker format is inferred from the **user's existing tracked docs**, not hardcoded.~~ — **amended by D20.** The template *is* the canon; conformance checking replaces structural inference. | This doc, 2026-07-21; amended 2026-07-22 | The tool checks trackers against `docs/PROJECT_DOC_TEMPLATE.md` and scaffolds from it. |
| D3 | Generated content lives inside `<!-- baseline:begin -->` / `<!-- baseline:end -->` marker blocks; hand-written prose is never clobbered. | TD4 fix (PR #31), 2026-07-21 | Reuses the existing marker-block system. |
| D4 | ~~Publishing targets are agent-specific~~ — **amended by D8.** The target list stands, but those files become thin adapters pointing at the canonical artifact, not copies of it. | Research, 2026-07-21; amended 2026-07-22 | One rule may still surface in multiple targets; only one place holds its text. |
| D5 | ~~Cross-agent consistency is enforced by the **tool**.~~ — **amended by D15.** True for *managed* agents (Claude, Codex) which reliably read an instruction file. Not assumed for unmanaged agents. | This doc, 2026-07-21; amended 2026-07-22 | Enforcement where a convention exists; publish-and-observe where it does not. |
| D6 | First PR is this doc + a `docs/README.md` index entry. Code follows after docs merge. | D4 from FIRST_USER_SETUP_TRACKER precedent | Docs-first workflow. |
| **D7** | **Propose-only by default. No surprises.** The tool proposes; adoption is gated on an explicit user action. Writes to any repo or file the tool does not own — including `/memories/` — require deliberate opt-in (`--fix`), never blanket approval. | Owner, 2026-07-22, issue #86 | Un-gates R4 and R7. Resolves §8 Q3 and Q5. This is the parent decision D8–D15 elaborate. |
| D8 | **Pull model, not push.** One canonical, user-level, read-only policy artifact that agents *consult*; per-agent files are thin adapters pointing at it. | Owner, 2026-07-22, issue #86 | Smaller blast radius, no N-way drift, revocation is "stop reading it" rather than "un-write N files". Amends D4. |
| D9 | **Two tiers.** `Rules` = strict, violation is an error. `Guidelines` = extra care, violation is a warning. | Owner, 2026-07-22, issue #86 | Maps directly onto `baseline lint` / `eval` severity, which is what makes the D14 scorecard meaningful. |
| D10 | **Concretely grounded and measurable only.** Every rule carries a detectability marker: `auto` (checkable from session content), `assisted` (needs repo state too), `manual` (human judgement, never auto-scored). | Owner, 2026-07-22, issue #86 | Without this the scorecard silently grades only the easy rules and reads as full coverage. It must always report what it could **not** evaluate. |
| D11 | **The Markdown master is hand-editable and tool-un-owned.** The machine-readable sidecar is generated *from* it, never the reverse. Every rule must pass `baseline lint` to be published; a failing rule is **quarantined, not fatal**. | Owner, 2026-07-22, issue #86 | The user keeps authorship; the gate keeps the quality bar. Fail-soft because the artifact sits on the path of every agent session. |
| D12 | **Two provenance classes, one quality bar.** `mined` (session evidence: ids, counts, agents) and `asserted` (owner + date). Both pass the same validator. | Owner, 2026-07-22, issue #86 | 4 of the 10 canonical preferences in §3.4 come from user memory, not sessions — a mined-only artifact would drop them. Traceable ≠ derived-from-sessions. |
| D13 | **The canonical artifact lives in the cross-machine synced store**, not beside any checkout. The gitignored local directory is a derived **cache**, never the master. | Owner, 2026-07-22, issue #86 | Follows the repo's own rule: "everything emitted is either a recipe (tiny, durable) or a cache (deletable); never a master." A checkout-local artifact cannot cross the work-laptop / personal-laptop boundary that is this project's USP. |
| D14 | **The compliance scorecard piggybacks `baseline eval`** behind a flag — no new command. Per-agent first, per-repo later. | Owner, 2026-07-22, issue #86 | Reuses the existing gate surface. |
| D15 | **Unmanaged agents are not assumed enforceable.** Router injection is consent-gated and read-only by default; feasibility is an open spike. | Owner, 2026-07-22, issue #86 | Grok / Gemini / DeepSeek / Z.AI may expose no injection point. Publish-and-observe still works without one, because this tool archives their sessions. Spike: `agent-session-router` #24. Amends D5. |
| D16 | **Architecture reconciled to the pull model.** The loop is extract → propose → owner-curated master → compile → eval. No component writes agent files directly; per-agent files are compiled thin adapters of the master. `AGENT_TARGETS` (`baseline_publish.py`) and the E5 efficacy gate move in the same PR as the compiler. | 2026-07-22 repo review, issue #99 (F1); owner-approved 2026-07-22 | §4 rewritten; R4 becomes master-schema + compiler; the D14 scorecard gets its own row (R11). |
| D17 | **Export-time extraction into a tracked evidence ledger.** Extraction hooks `export` — the only moment a session body is guaranteed present on the exporting machine; redacted evidence appends to tracked `baseline/evidence/rules.jsonl`, union-merged by stable id across machines (the `archive/index.jsonl` / handoff-index pattern). Resolves §8 Q1. | 2026-07-22 repo review, issue #99 (F2); owner-approved 2026-07-22 | Machine-local body visibility (0 bodies on the review checkout vs 5,438 catalog records) stops biasing scores; the analysis layer becomes incremental; redaction-v1 gates every ledger write. |
| D18 | **Echo-contamination controls.** Extraction is role-aware; marker-block content and known instruction-file text are excluded; evidence is tagged `novel` vs `echo`; **saturation rule** — text present in ≥80% of one agent's sessions is echo-suspect regardless of role (spike-verified: instruction injections arrive under `user`/`developer` roles). Echoes never count as fresh evidence or as compliance. | 2026-07-22 repo review, issue #99 (F3); spike evidence 2026-07-22; owner-approved | `RawRule` carries `role` + novelty; the scorecard excludes echoes; new §5 risk row. |
| D19 | **Polarity + topic-token clustering; contradictions are an output.** Candidates normalize to (polarity, topic-token-set); clusters form on token overlap; same-topic + opposite-polarity pairs are the contradiction report, feeding `P6-contradiction`. Edit distance is demoted to tie-breaker. Supplies the mechanism for §8 Q2. | 2026-07-22 repo review, issue #99 (F5); owner-approved 2026-07-22 | R2 reshaped; §1.3 good-looks-like #4 becomes a deliverable instead of a casualty of the algorithm. |
| D20 | **Template-as-canon (amends D2).** `docs/PROJECT_DOC_TEMPLATE.md` *is* the canonical tracker signature; R6 checks conformance against it and scaffolds from it; the template ships with the canonical artifact for cross-repo use. | 2026-07-22 repo review, issue #99 (F6); owner-approved 2026-07-22 | No structural inference; the H9-normalized docs become test fixtures rather than training data. |
| D21 | **Adapter context budget.** Compiled adapters are tier-ranked (D9) and capped at top-N rules by score, with a pointer to the full master. | 2026-07-22 repo review, issue #99 (F7); owner-approved 2026-07-22 | Published rules never bloat the context of the agents they serve. |
| D22 | **Master snapshots versioned in-repo.** Each compile writes a redacted snapshot of the master into this repo (tracked) for diff/history/review; the synced-store copy stays the distribution point. D13 unchanged. | 2026-07-22 repo review, issue #99 (F7); owner-approved 2026-07-22 | Rule changes get git history and PR review without changing where agents read. |
| D23 | **Precision-hardening is sequenced before R3.** The 2026-07-23 efficacy run (1,125 real sessions) showed the pipeline recalls 8/10 canonical rules but *ranks* agent-authored boilerplate above user preferences; a user-role-only lens surfaced the genuine rules. So R2a (role-privileged scoring), R2b (D18 saturation as a score penalty), R2c (extraction code/log filtering) land before R3 — classifying noise-dominated clusters is premature. | Owner-approved 2026-07-23, mid-project efficacy run | R2a–R2c inserted ahead of R3; baseline metrics preserved in `docs/EFFICACY_CHECK_2026-07-23.md` for post-fix comparison. Validates D18. |

---

## 3. Foundation — research / prior art

### 3.1  What sessions already contain

Mined 2026-07-21 from 5,438 sessions (newest 50 sampled):

| Pattern | Occurrences | Example |
|---|---|---|
| `always` / `never` imperatives | 200+ hits across 35 sessions | "never train on paid-llm outputs", "always bake the ops-agent startup-script" |
| `rule` / `guardrail` / `convention` | 300+ hits across 45 sessions | "the guardrail is never train on paid-llm outputs" |
| `memory` references | 200+ hits across 20 sessions | "pointer in memory `current-state`", "memory says the migration was done" |
| `instruction` / `.instructions.md` | 100+ hits across 8 sessions | "this document states the invariants the engine must satisfy" |
| `SKILL.md` / skill folder references | 15+ sessions | Agent customization skill discussions |

[verified] Concrete rules found in sessions (not captured by current tool):

1. "never train on paid-llm (gemini/openai/anthropic) outputs" — discussed in 8+ sessions, audited in code
2. "provenance must travel with the label, computed at the point of claim" — design rule
3. "the default must be safe and bounded for the system; never make the default the option that can cost the user"
4. "defer the decision to the last responsible moment"
5. "everything emitted is either a recipe (tiny, durable) or a cache (deletable); never a master"
6. **"never auto-merge PRs — wait for explicit owner LGTM, and only after CI is green"** — found in `AGENTS.md` (the working agreement), reinforced across Claude + Codex sessions spanning 2+ projects.  The user's `AGENTS.md` states: *"Wait for review comments or an explicit LGTM before merging. Merge only after the PR has LGTM or explicit owner approval scoped to that PR. If a tool cannot formally approve because the PR author and reviewer are the same GitHub account, require an explicit owner LGTM comment or instruction before merge."*

### 3.2  Existing infrastructure to build on

| Component | File | What it provides |
|---|---|---|
| Keyword scanning | `baseline_predictions.py` | Regex-based text signal extraction (reuse pattern for imperative-statement regex) |
| Marker-block upsert | `baseline_promote.py` | `_upsert_marker_blocks()` for idempotent content injection |
| Agent-target rendering | `baseline_publish.py` | `AGENT_TARGETS` mapping + `render_agent_document()` (extend with rule templates) |
| Cross-session indexing | `baseline_handoffs.py` | `build_handoff_index_records()` shows how to scan, dedup, and write persistent index |
| Recency weighting | `utils.py` | `session_recency_weight()`, `most_recent_first()` for freshness-aware scanning |
| Canonicalization | `utils.py` | `canonical_agent()` maps per-machine sources to canonical agents |

### 3.3  Agent knowledge formats

[researched] Each agent consumes instructions differently:

| Agent | Primary file | Secondary | Marker format | Scope |
|---|---|---|---|---|
| **Claude Code** | `CLAUDE.md` (project root) | `/memories/` (user) | Markdown with `##` sections | Per-project |
| **Codex CLI** | `AGENTS.md` (project root) | `.codex/instructions.md` | Markdown bullet lists | Per-project |
| **VS Code Copilot** | `.instructions.md` | `.prompt.md`, `SKILL.md` | YAML frontmatter + Markdown | Per-project or user |
| **GitHub Copilot** | `copilot-instructions.md` | `.github/instructions/*.md` | Markdown | Per-repo |
| **User memory** | `/memories/patterns.md` | `/memories/repo/<slug>.md` | Markdown bullet lists | Cross-workspace |
| **Skills** | `<skill>/SKILL.md` | YAML frontmatter | `applyTo` patterns | Domain-specific |

---

### 3.4  Concrete cross-project, cross-agent preferences found

[verified] Mining 2026-07-21 against 5,438 sessions (207 locally available, 500 newest sampled):

| # | Preference | Sessions | Projects | Agents | Source |
|---|---|---|---|---|---|
| 1 | **Never auto-merge PRs** — wait for explicit owner LGTM; only after CI green | 3 sessions + `AGENTS.md` | 2+ | Claude + Codex | `AGENTS.md` working agreement |
| 2 | **Maintain SESSION_HANDOFF.md** for agent resume | 22 | 7 | Claude + Codex | Session content |
| 3 | **Use tracked project docs** (§7, status headers, decisions table) | 24 | 7 | Claude + Codex | Session content |
| 4 | **One small PR per deliverable row** | 67 | 11 | Claude-dominant | Session content |
| 5 | **Never train on paid-LLM outputs** | 37 | 5 | Claude-dominant | Session content |
| 6 | **Always branch from main, never commit directly** | Present in `/memories/patterns.md` | All | All | User memory |
| 7 | **Always verify CI is green before moving on** | Present in `/memories/patterns.md` | badminton-highlight-indexer, agent-sessions | All | User memory |
| 8 | **Format-on-save pollutes diffs — bypass editor** | Present in `/memories/patterns.md` | badminton-highlight-indexer | All | User memory |
| 9 | **isort import grouping (stdlib → third-party → first-party)** | Present in `/memories/patterns.md` | badminton-highlight-indexer | All | User memory |
| 10 | **Mypy catches things Ruff doesn't** | 3 | 3 | Claude-dominant | Session content |

These 10 preferences are the **canonical set** the tool should detect and enforce
across all projects and agents.  Preferences #1–#5 are the highest priority
because they span the most projects and have the strongest cross-agent signal.

**Corpus distribution** [verified 2026-07-22]: of the 5,438 catalog records —
claude 2,745, deepseek 2,603 (request dumps, not conversations), codex 61,
grok 25, gemini 4; mtime window 2026-05-30 → 2026-07-21.  "Cross-agent"
therefore means claude+deepseek in practice today; scoring must disclose the
imbalance rather than let a cross-agent bonus imply five-agent consensus.

---

## 4. Design / architecture

### 4.1  Rule pipeline — reconciled to D7–D15 by D16/D17 (issue #99)

The pre-review §4.1 described a push-model publisher writing "updated files on
disk"; that contradicted D8/D11 and was replaced 2026-07-22.

```text
export (runs per machine — the session body is guaranteed present, D17)
  │
  ├─[1] rule_extractor.py — role-aware imperative parse (D18)
  │     → RawRule(text, session_id, project, agent, role, novelty, mtime)
  │     → redaction-v1 gate → append baseline/evidence/rules.jsonl
  │       (tracked; union-merged by stable id across machines, the same
  │        pattern as archive/index.jsonl and baseline/handoffs/index.jsonl)
  │
  ├─[2] rule_clusterer.py — (polarity, topic-token-set) clustering (D19)
  │     score = frequency × recency × imbalance-disclosed cross-agent factor
  │     contradiction pairs = same topic, opposite polarity → P6 lint
  │
  ├─[3] rule_classifier.py — scope (global | project:<slug> | repo:<path>),
  │     Prediction-id links, user-memory comparator,
  │     detectability marker auto|assisted|manual (D10)
  │
  ├─[4] propose — candidate rules + evidence for owner review (D7);
  │     nothing outside baseline/ is written
  │
  ├─[owner] curate the master — hand-edited Markdown, synced store (D11, D13)
  │
  ├─[5] compile — master → machine-readable sidecar + thin per-agent
  │     adapters (context-budgeted top-N, D21) + in-repo redacted
  │     snapshot (D22); AGENT_TARGETS and the E5 gate move in the
  │     same PR (D16); marker blocks never clobber hand-written prose (D3)
  │
  └─[6] eval — compliance scorecard behind a `baseline eval` flag (D14):
        per-agent, echo-excluded (D18), detectability-aware with an
        explicit not-evaluated set (D10), staleness flags from
        last-evidenced dates (the W3-stale pattern)
```

### 4.2  Tracker conformance & scaffolding (D20)

```text
docs/PROJECT_DOC_TEMPLATE.md   ⟵ the canonical signature (D20)
  │
  ├─ conformance check per project tracker:
  │     - status header present      (Status / Owner / Created / Updated)
  │     - decisions-locked table     (| # | Decision | …)
  │     - §7 deliverable rows        (| ID | Deliverable | …)
  │     - lifecycle tag              (DRAFT → IN PROGRESS → DONE → archived)
  │
  ├─ report gaps: missing tracker, missing sections, stale status
  │
  └─ scaffold from the template for a project without a tracker —
        only with explicit opt-in (--fix, D7)
```

### 4.3  Cross-agent enforcement

The **template** is the single source of truth for tracker format; the tool is
its conformance mechanism (D20) — for managed agents; unmanaged agents remain
publish-and-observe (D15).  When any agent starts work on a project:

1. The tool detects the project (from cwd or session metadata).
2. It checks whether a tracker exists and conforms to the template.
3. If missing, it proposes a scaffold (writing requires `--fix`, D7).
4. If present but stale or non-conformant, it flags a warning.
5. The agent reads the tracker and follows its §7 rows.

This means the user does not need to tell each new agent "use my tracker format" —
the tool enforces it automatically.

---

## 5. Threat model / risk table

| Risk | Mitigation |
|---|---|
| Rule extraction produces false positives (flagging non-rules as rules). | Confidence threshold (≥3 sessions, ≥2 agents) before a rule is promoted. Human-gated promotion (same as existing guardrails). |
| Clustered rules lose nuance (different projects need different versions of "always run tests"). | Project-scoped rules are kept separate from global rules. Global rules only when the same text appears across ≥3 projects. |
| Generated instruction files overwrite hand-written content. | Marker-block system (D3): generated content lives inside `<!-- baseline:begin -->` blocks; hand-written prose outside is preserved. |
| Tracker format detection fails on a novel format. | Superseded by D20: conformance is checked against `PROJECT_DOC_TEMPLATE.md` directly; no inference to fail. Human override via config. |
| Cross-agent publishing creates conflicting instructions. | Publish only to agent targets that exist; flag contradictions in `baseline lint`. |
| Instruction-file echo inflates mined counts after publication — agents inject `CLAUDE.md`/`AGENTS.md` into context; 48% of the corpus is DeepSeek request dumps; spike-verified that echoes arrive under `user`/`developer` roles. | D18: role split + ≥80% saturation rule + known-instruction exclusion; echoes tagged and never scored as fresh evidence or compliance. |
| Any single machine sees only its local transcript bodies (0 on the review checkout vs 5,438 catalog records), biasing frequency and agent thresholds. | D17: export-time extraction + tracked union-merged evidence ledger; scores computed only over the merged ledger. |
| The tracked evidence ledger crosses machines and could leak paths/secrets the way `archive/index.jsonl` did (deferred to #93). | Redaction-v1 (fail-closed) gates every ledger append; blocked lines are quarantined, mirroring D11's fail-soft stance. |
| Token clustering can still merge opposites if polarity is missed, or split heavy paraphrases. | D19: polarity normalization runs first; same-topic opposite-polarity pairs are surfaced for human review, never silently merged; R2 tests cover near-opposite fixtures. |
| Corpus imbalance (claude+deepseek = 98%) oversells "cross-agent" consensus. | Scores disclose per-agent counts; the cross-agent factor is damped while the corpus is effectively two-agent (§3.4). |

---

## 6. Honest limits — what this does NOT do

- **No LLM-based rule generation.** Extraction is regex + clustering only (D1).
- **No automatic promotion.** Rules go through the same human-gated pipeline as guardrails.
- **No semantic understanding of rules.** The tool does not "understand" that "never push to main" and "always use a branch" are the same rule — deterministic polarity + token-overlap clustering (D19) narrows but does not remove this limit.
- **No modification of agent behavior at runtime.** The tool compiles adapters; agents must be configured to read them (D8, D15).
- **No real-time enforcement.** Extraction runs during `export` (D17) and proposal during `baseline rules extract`, not as a pre-commit hook or runtime monitor.
- **No echo-proof guarantee.** The D18 role/saturation heuristics reduce instruction-echo contamination; they cannot eliminate it. The scorecard always discloses what was excluded and what it could not evaluate (D10).

---

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated. **One small PR per row.**

| ID | Deliverable | Depends on | Gated? | Status | PR |
|---|---|---|---|---|---|
| R0 | This tracked project doc, `docs/README.md` index entry, and `SESSION_HANDOFF.md` pointer. | — | No | ☑ | #79, #80 |
| R1a | **Validation spike (D1 evidence):** throwaway deterministic extract+cluster dry-run (`tools/rules_extract_spike.py`), read-only over locally reachable raw stores; measures recall against the §3.4 canonical set, role split, and echo saturation; numbers recorded in this doc's changelog and issue #99. Owner then confirms or revisits D1 on that evidence. | R0 | No | ☑ | #102 |
| R1 | `agent_sessions/rule_extractor.py`: role-aware imperative parser (D18) invoked from `export` (D17); `extract_rules()` returns `list[RawRule]` with session + agent + project + `role` + `novel\|echo` provenance. Tests with fixture transcripts. | R1a | No (H1–H8 ☑ 2026-07-22) | ☑ | #103 |
| R1b | Evidence ledger: tracked `baseline/evidence/rules.jsonl` — stable-id union merge across machines (the `merge_index_records` / handoff-index pattern), every line gated through redaction-v1 before append (D17). Tests incl. cross-machine merge and redaction-refusal fixtures. | R1 | No | ☑ | #104 |
| R2 | `agent_sessions/rule_clusterer.py`: (polarity, topic-token-set) clustering with token-overlap similarity (D19); emits clusters **and contradiction pairs** (same topic, opposite polarity); score = frequency × recency × imbalance-disclosed cross-agent factor (§3.4). Edit distance as tie-breaker only. Tests with paraphrase, near-opposite, and echo fixtures. | R1b | No | ☑ | #107 |
| R2a | **Role-privileged scoring** (D23, efficacy fix #1): in `rule_clusterer`, weight user-authored evidence far above `system`/`developer`/`request-prompt`/`assistant` roles so genuine preferences outrank agent boilerplate. Frequency counts user-role novel sessions primarily. Tests assert the user-role lens ranks canonical rules first. | R2 | No | ☐ | — |
| R2b | **D18 saturation as a first-class score penalty** (D23, efficacy fix #2): thread per-agent session totals into `cluster_rules`; a cluster in ≥80% of one agent's sessions is penalized/excluded in scoring, not merely flagged in a post-filter. Removes the ~100%-saturation injected system prompts before they rank. Tests with a saturated-echo fixture. | R2a | No | ☐ | — |
| R2c | **Extraction hygiene** (D23, efficacy fix #3): in `rule_extractor`, exclude code/log/banner lines (line-numbered code, `//`/`#` comment lines, `=== … ===` banners, bare `</tag>` fragments) from sentence extraction; optionally accept agent system prompts as `known_instruction_texts` for echo tagging (fix #4). Tests with code/log fixtures. | R1 | No | ☐ | — |
| R3 | `agent_sessions/rule_classifier.py`: scope classifier (global/project/repo), prediction-ID linker, user-memory comparator, **detectability marker** per rule (`auto\|assisted\|manual`, D10). `classify_rules()` returning `list[ClassifiedRule]`. | R2a, R2b, R2c | No | ☐ | — |
| R4 | Canonical master schema + **compiler** (D16): hand-editable master (D11) in the synced store (D13) → machine sidecar + thin per-agent adapters (context-budgeted top-N, D21) + in-repo redacted snapshot (D22). Replaces the push-model publisher; updates `AGENT_TARGETS` **and the E5 gate in the same PR**. Propose-only (D7). | R3 | No | ☐ | — |
| R5 | `baseline rules extract` CLI command: wires extract → cluster → classify → **propose** (D7); `--max-sessions`, `--dry-run` (default), `--output`. Integration test against a fixture corpus. | R4 | No | ☐ | — |
| R6 | Tracker conformance (D20): `agent_sessions/tracker_detector.py` checks projects against `docs/PROJECT_DOC_TEMPLATE.md` (status header, decisions table, §7 rows, lifecycle) and scaffolds from the template. No structural inference. | R0 | No (H9 ☑ 2026-07-22) | ☐ | — |
| R7 | `baseline tracker enforce` CLI command: reports conformance gaps across projects; writes scaffolds only with `--fix` (explicit opt-in per D7). | R6 | No | ☐ | — |
| R8 | Cross-agent consistency gate: `baseline lint` extension that flags projects with no conformant tracker and **R2 contradiction pairs** (feeding `P6-contradiction`). New efficacy gate `G-tracker-consistency`. | R6, R7 | Yes | ☐ | — |
| R9 | Integration (D17): extraction runs during `export` on each machine; `baseline suggest` consumes the merged ledger (no body re-scan); `--skip-rules` opt-out. | R5 | Yes | ☐ | — |
| R10 | Dogfood: extract from this repo's own archive, propose into its AGENTS.md / CLAUDE.md adapters, verify against `/memories/patterns.md`, and confirm echo-tagging keeps published-rule evidence counts flat after publication (D18). | R5, R7 | No | ☐ | — |
| R11 | **Compliance scorecard (D14):** `baseline eval` flag reporting per-agent rule compliance from ledger evidence — detectability-aware (D10), **always reporting the not-evaluated set**, staleness flags from last-evidenced dates (W3 pattern). Per-agent first, per-repo later. | R1b, R4 | No | ☐ | — |

---

## 8. Open questions — owner / external

1. ~~**Should rule extraction run on every `baseline suggest`, or be a separate command?**~~ **RESOLVED 2026-07-22 (D17, issue #99 F2):** neither — extraction runs at **export time**, the only moment a session body is guaranteed present on the exporting machine; `baseline suggest` consumes the merged ledger. `--skip-rules` opts out.
2. ~~**How should the tool handle rules that differ by project?**~~ **RESOLVED 2026-07-22 (D19, issue #99 F5):** project-scoped rules take precedence over global, as proposed; the mechanism is polarity+topic clustering — same-topic opposite-polarity pairs are flagged as contradictions for human resolution, never silently merged.
3. ~~**Should the tool write to `/memories/` directly, or only propose?**~~ **RESOLVED 2026-07-22 (D7):** propose-only, always, for every target — not just memory. Adoption is gated on an explicit user action; `--fix` is deliberate opt-in, never blanket approval.
4. **What is the minimum confidence for auto-promotion?**  [design] Currently none; all promotion is human-gated.  Proposed: rules with ≥10 sessions, ≥3 agents, ≥0.95 confidence can be auto-proposed into a "suggested" section that the user reviews.
5. ~~**Should tracker enforcement be opt-in per project, or automatic?**~~ **RESOLVED 2026-07-22 (D7):** opt-in. Detection and reporting may run anywhere; *writing* a scaffold into a repo the tool does not own requires explicit opt-in. The `[tracker] enforce = true` setting stands as the opt-in mechanism.

---

## 9. Definition of done

- [ ] R0–R11 (including R1a/R1b) all merged with passing gates (pytest, ruff, mypy, coverage ≥ floor).
- [ ] R1a spike numbers recorded (recall on the session-derivable §3.4 subset, echo-saturation split) and the owner's keep/revisit call on D1 noted in §2.
- [ ] Export-time extraction on ≥2 machines union-merges into `baseline/evidence/rules.jsonl` without loss; every ledger line passed redaction-v1; catalog-scale coverage (the 5,438-record catalog) is reached **across machines**, never claimed from a single run (D17 — the pre-review "runs against 5,438 sessions" wording was impossible on any one machine).
- [ ] Mined rules match ≥80% of the **session-derivable** subset of `/memories/patterns.md`; asserted rules (D12) are preserved in the master and never dropped by mining (the pre-review flat ≥80% was unachievable: 4 of 10 canonical preferences exist only in user memory).
- [ ] The contradiction report surfaces same-topic opposite-polarity pairs (§1.3 #4) and feeds `P6-contradiction`.
- [ ] Compiled adapters are valid CLAUDE.md / AGENTS.md / .instructions.md snippets within the D21 context budget; the marker-block golden test preserves hand-written prose; `AGENT_TARGETS` and E5 updated in the compiler PR (D16).
- [ ] `baseline tracker enforce` verifies conformance against `docs/PROJECT_DOC_TEMPLATE.md` and scaffolds a missing tracker from it (D20).
- [ ] `baseline lint` includes the new `G-tracker-consistency` gate; the `baseline eval` scorecard reports per-agent compliance **and the not-evaluated set** (D10/D14).
- [ ] This tracker doc is moved to `docs/archives/` with a DONE status.

---

## 10. References

**Internal:**
- `docs/archives/BASELINE_KNOWLEDGE_REPLAY_PLAN.md` — K0–K12 pipeline this extends
- `docs/ENGINEERING_BASELINE.md` — baseline architecture
- `docs/CALIBRATION_EFFICACY.md` — efficacy gates E1–E6
- `docs/PROJECT_DOC_TEMPLATE.md` — this doc's template source
- `docs/EFFICACY_CHECK_2026-07-23.md` — mid-project efficacy baseline (metrics for post-fix comparison)
- `tools/rules_demo.py` — the reproducible efficacy harness (real modules, real sessions)
- `/memories/patterns.md` — existing manually-curated rules (ground truth)
- `agent_sessions/baseline_predictions.py` — keyword scanning (reuse)
- `agent_sessions/baseline_promote.py` — marker-block upsert (reuse)
- `agent_sessions/baseline_publish.py` — agent-target rendering (extend)

**External:**
- Claude Code memory/CLAUDE.md: `https://docs.anthropic.com/en/docs/claude-code`
- VS Code Copilot instructions: `https://code.visualstudio.com/docs/copilot/copilot-customization`
- Codex AGENTS.md: `https://github.com/openai/codex`

### Changelog
- `2026-07-23` — **Mid-project efficacy run → precision-hardening reprioritized (D23).** Ran the shipped R1→R1b→R2 pipeline on **1,125 real sessions** (5 agents): 47,126 imperative statements → 39,661 redacted evidence records (**43 secrets quarantined**), 6,490 clusters, 7 contradictions, **8/10 ground-truth recall (6/6 session-derivable)**. Mechanics sound and redaction held, but the default ranking scores agent-authored boilerplate (DeepSeek/Copilot system prompts, MCP/skill descriptions) above user preferences — a user-role-only lens surfaced the genuine rules (one-PR-per-row, never-push-to-main, never-train-on-paid-LLMs, stage-explicit-paths). Added rows **R2a** (role-privileged scoring), **R2b** (D18 saturation as a score penalty), **R2c** (extraction code/log filtering) ahead of R3, since R3 classifies R2's output. Baseline metrics preserved in `docs/EFFICACY_CHECK_2026-07-23.md`; reproducible harness at `tools/rules_demo.py`; illustrative examples in the owner's private artifact.
- `2026-07-23` — **R2 ☑ (#107) — clusterer.** `agent_sessions/rule_clusterer.py`: reads the R1b evidence ledger and groups records by **(polarity, topic-token overlap)** — Jaccard ≥ 0.5 against the seed member's cleaned token set, never edit distance (D19), so opposites don't merge and paraphrases don't split. `cluster_rules()` returns scored `ClusteredRule`s; `find_contradictions()` returns same-topic/opposite-polarity `ContradictionPair`s (the D19 flagship, feeding P6 lint). **Score = novel-session frequency × recency × imbalance-disclosed cross-agent factor:** echoes (D18) still cluster but only `novel` evidence counts toward frequency and the cross-agent factor — an all-echo cluster scores 0 — and the factor only grows for agents carrying ≥2 novel sessions, so a lone drive-by from a rare agent can't imply cross-agent consensus on a claude+deepseek-heavy corpus (§3.4); every `ClusteredRule` carries the full `per_agent_sessions` breakdown so the imbalance is visible, not hidden in one number. Resolves the `repo.`-vs-`repo` trailing-punctuation artifact flagged in R1's review by stripping end-punctuation from tokens at the clusterer (not the extractor). Deterministic and order-independent (inputs sorted before greedy assignment). Covered by `tests/test_rule_clusterer.py` (21 cases: paraphrase clustering, distinct-topic separation, the trailing-punctuation fix, cross-agent scoring + damping, echo-only-scores-zero, contradiction detection incl. same-polarity/unrelated negatives, session dedup, determinism, ledger integration). Gates green via `local_ci.sh`: ruff, mypy, md-links, **734 passed**, coverage 96.96%.
- `2026-07-23` — **R1b ☑ (#104) — evidence ledger.** `agent_sessions/rule_ledger.py`: `EvidenceRecord` + tracked `baseline/evidence/rules.jsonl` (the `*.json` ignore glob does not match `.jsonl`, verified via `git check-ignore`).  Reuses the handoff-index pattern verbatim — `stable_rule_id` = `rule.<sha256(agent:session_id:role:normalized)[:12]>`, `merge_evidence_records` union-merges by id with the current run winning, `render_ledger_jsonl` emits `sort_keys` lines sorted by `(agent, project, normalized, id)`.  **D17 redaction gate:** every rule passes `redact_text` before entry; a high-confidence secret **quarantines** the rule (dropped + counted, fail-soft per D11), and the stored text/`normalized`/id are all recomputed from the *redacted* text so a home-dir username cannot leak through a derived field (a real property confirmed in tests: `/home/alice/env.sh` and `/home/bob/env.sh` collapse to one id because redaction-v1 placeholders the `/home/<user>` prefix).  `occurrences` counts within-session repeats; `redaction_placeholders` stores counts only, never values.  `update_ledger` is the load→build→merge→write entry point returning `(total, added, quarantined)` for the export/CLI report — the export auto-hook itself is R9.  Covered by `tests/test_rule_ledger.py` (27 cases: stable-id components, quarantine + no-secret-in-text, path placeholdering, cross-machine collapse, current-wins merge, idempotent re-run, serialization round-trip, IO).  Gates green via `local_ci.sh`: ruff, mypy, **705 passed**, coverage 96.77% (module 100%).
- `2026-07-23` — **D1 confirmed; R1 ☑ (#103).** Owner reviewed the R1a evidence and posted LGTM on issue #99 — D1 (deterministic extraction) stands.  R1 ships `agent_sessions/rule_extractor.py`: role-aware imperative parser returning `list[RawRule]` (text, normalized form, polarity, sorted topic tokens, `role`, `novel|echo`, session/agent/project/mtime); per-session and stateless so `export` can invoke it while the body is guaranteed present (D17 — the auto-hook itself is R9's row).  D18 at this layer: `<!-- baseline:... -->` marker blocks (promotion **and** `generated:` variants) are stripped before mining, and sentences matching caller-supplied known instruction texts are tagged `echo` through the same normalizer used for clustering; the ≥80% saturation rule stays corpus-level (R1b/R2), per the spike's false-negative finding.  Covered by `tests/test_rule_extractor.py` (34 cases: sentence filters, polarity cues, normalization determinism, marker stripping incl. known-set exclusion, echo tagging, provenance from Windows/POSIX `cwd`, ordering determinism).  Gates green via `local_ci.sh` (ruff, mypy, full suite, coverage ≥ 92).
- `2026-07-22` — **R1a ☑ (#102) — full-corpus spike run.** Corpus: 1,297 sessions across 5 agents (claude 539, codex 136, deepseek 600, grok 20, gemini 2; newest-first, per-source-root cap 600), 7,880 unique candidates → 3,681 clusters, 73 echo-suspect.  **Recall: 6/6 session-derivable §3.4 preferences — unchanged after excluding echo-suspect clusters** — plus 2/4 memory-only asserted items (gt6 branch-from-main, gt7 ci-green); gt8/gt9 missed exactly as D12/F4 predicted (they exist only in user memory, which is why the DoD separates asserted preservation from mined recall).  **Echo contamination confirmed at full scale:** the top 31 clusters by score are all instruction-file text — global `CLAUDE.md`/`AGENTS.md` working-agreement lines, MCP tool descriptions, DeepSeek/Copilot system-prompt boilerplate — arriving under `user`/`request-prompt` roles, so role-weighting alone cannot filter them; the D18 ≥80% saturation rule catches them, and a false-negative band just under threshold (skill text at ~72% saturation) confirms R1 must also implement D18's known-instruction-text exclusion, not saturation alone.  Contradiction detection emitted 1 mechanically correct same-topic opposite-polarity pair.  **Net: the D1 evidence is in and favorable — deterministic extraction recovers the full session-derivable canonical set; the owner's keep/revisit call on D1 (§9) is now unblocked.**  Spike script committed as `tools/rules_extract_spike.py`; full report retained locally (mined text stays off the tracked tree per D17's redaction stance); summary posted to issue #99.
- `2026-07-22` — **Course corrections D16–D22 locked** from the 2026-07-22 repo review (issue #99; review by Claude Fable 5 at the owner's request; adoption owner-approved the same day).  §4 rewritten to the pull-model loop (extract → propose → curate → compile → eval) — the prior §4.1/§7 predated D7–D15 and still specified the push-model publisher D8 rejected.  Rows added: R1a (D1 validation spike), R1b (tracked merge-aware evidence ledger), R11 (D14 scorecard).  Rows reshaped: R1 (role-aware, export-hooked), R2 (polarity+topic clustering, contradiction pairs), R3 (detectability markers), R4 (master schema + compiler; `AGENT_TARGETS` + E5 move together), R6 (template conformance per D20), R9 (export-time integration), R10 (echo regression check).  §5 gains echo/visibility/ledger-leak/imbalance risks; §6 limits updated; §8 Q1 resolved by D17 and Q2 by D19; §9 DoD restated (mined-recall on the session-derivable subset; asserted preservation; multi-machine ledger coverage).  D2 amended by D20.  A smoke run of the R1a spike (2026-07-22; 120 sessions, claude+codex) already recalled 6/6 derivable §3.4 preferences **and** empirically confirmed F3: the top clusters were instruction-file echoes arriving under `user`/`developer` roles — the reason D18 includes the ≥80% saturation rule.  R1a set to ◐ (spike script drafted and smoke-tested; full-corpus run and report pending).
- `2026-07-22` — **Gates cleared** (truth-up): `docs/FOUNDATION_HARDENING_PLAN.md` went DONE with H0–H11 all merged, so R1 (was ⛔ on H1–H8) and R6 (was ⛔ on H9) flipped to ☐ ready; status header updated to un-gated. `SESSION_HANDOFF.md` refreshed in the same PR — it still described H0 as in progress. A 2026-07-22 repo review (issue #99) proposed course corrections to this plan; they land in a follow-up tracker-revision PR, not this truth-up.
- `2026-07-22` — **D7–D15 locked** from owner decisions in issue #86, resolving §8 Q3 and Q5 and un-gating R4 and R7.  Propose-only is now the parent principle; the publishing model flips from push to pull (D8); rules gain tiers (D9), detectability markers (D10), a hand-editable master with a lint gate (D11), and two provenance classes (D12); the artifact moves to the cross-machine synced store (D13).  D4 and D5 amended rather than deleted.  Delivered by hardening row H11.
- `2026-07-22` — R0 marked ☑ (delivered by #79 and #80; the row was left unchecked at merge).  R1, R4, R6, R7 marked ⛔ gated on `docs/FOUNDATION_HARDENING_PLAN.md`: R1 on H1–H8 (foundation-first, D1), R4/R7 on H11 (propose-only writes to repos this tool does not own), R6 on H9 (doc lifecycle must be consistent before the detector learns the canonical format from it).
- `2026-07-21` — Created.  R0–R10 scoped based on session mining and owner feedback.
