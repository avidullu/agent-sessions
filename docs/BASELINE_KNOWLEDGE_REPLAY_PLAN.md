# Baseline Knowledge + Replay Plan

> **Status:** `DRAFT` - design review for issues #23, #25, and #26. **Owner:** `avidullu`. **Created:** `2026-07-07`. **Last updated:** `2026-07-07`
> **Lifecycle:** `DRAFT -> IN PROGRESS -> DONE -> archived`
> **Tracking anchors:** Section 7 is the source of truth; indexed in `docs/README.md`; pointer in `SESSION_HANDOFF.md`.
> **Relation to existing docs:** extends `docs/BASELINE_LOOP_CLOSURE.md`, `docs/CALIBRATION_EFFICACY.md`, and `docs/COMPOSE_STACK.md`; treats issue #19 as a shared provenance dependency.
> **Honesty note:** claims marked `[verified]` were checked against this repo or the linked issue text; `[researched]` items come from external sources in Section 10; `[design]` items are not implemented yet.

---

## 0. TL;DR

Build the compounding knowledge layer first, then handoff mining, then replay.
The shared substrate is a deterministic, human-gated `baseline/SCHEMA.md` plus
compiled project pages with marker-owned blocks and lint gates. Handoff mining is
the lowest-risk first producer because handoffs are already distilled session
memory; replay comes after schema, provenance, redaction, and bundle contracts are
in place.

## 1. Problem & goal

**Problem:** the baseline loop can ingest structured proposals and publish
reviewed guardrails, but it does not yet compound project knowledge, mine the
repo's own handoff conventions, or replay archived sessions to compare alternate
agent outputs. Issues #23, #25, and #26 are three faces of the same product:
turn archived work into reviewable knowledge that improves future sessions
without giving an LLM silent write access to policy.

**Goal:** a safe knowledge-and-replay pipeline where:

1. Project pages accumulate durable, cross-linked knowledge with explicit
   provenance.
2. Session handoffs become normalized evidence records and proposal inputs.
3. Replay packets can be generated deterministically, executed out-of-band by a
   different agent or panel, and ingested only as human-reviewable proposals.
4. Lint, calibration, and promotion gates prove the loop compounds knowledge
   instead of rewriting history.

## 2. Decisions locked

| # | Decision | Source / date | Implication |
|---|---|---|---|
| D1 | Do `baseline/SCHEMA.md` before mining or replay. | #26 + research, 2026-07-07 | Every derived artifact gets ownership, provenance, and lint rules before new producers write into it. |
| D2 | Keep raw sources immutable and derived pages deterministic. | LLM-wiki prior art `[researched]` | Use marker-block upserts and generated sections; do not let an LLM freely rewrite project pages. |
| D3 | Ship handoff mining before replay. | #23/#25 scope comparison `[design]` | Handoffs are already summary artifacts, so they validate schema/provenance with less execution risk. |
| D4 | Replay execution is out-of-band in v1. | #25 + eval tooling research `[researched]` | This repo selects and bundles sessions; another agent/panel runs the replay and submits structured output. |
| D5 | Exclude coding sessions from replay v1. | #25 non-goal `[verified]` | No workspace snapshots means code replay would be misleading until commit/worktree provenance exists. |
| D6 | Add lightweight provenance now; integrate deeper #19 traces later. | #19 dependency `[design]` | Record source entity, activity, agent, derivation, and bundle ids without blocking on a full trace system. |
| D7 | Do not build search or embeddings for v1. | `docs/COMPOSE_STACK.md` + #23/#26 non-goals `[verified]` | Use deterministic indexes, JSONL manifests, and markdown pages; search/live memory stays external. |

## 3. Foundation - research and prior art

| Source | Useful takeaway | Design consequence |
|---|---|---|
| LLM-wiki concept `[researched]` | Keep raw sources as immutable input, maintain structured interlinked markdown, and use schema/index/lint conventions. | `baseline/SCHEMA.md`, project-page marker blocks, page indexes, stale/orphan/contradiction lint. |
| Reflexion `[researched]` | Verbal reflections can improve later agent behavior without changing model weights. | Treat handoffs and replay judgments as reflection-like evidence, not as automatic policy. |
| Generative Agents `[researched]` | Experiences can be stored, reflected into higher-level summaries, and retrieved for planning. | Separate raw archive, normalized records, synthesized project pages, and future prompt packets. |
| Contextual Experience Replay `[researched]` | Past experiences can be accumulated and synthesized into a memory buffer for training-free improvement. | Replay and handoff outputs should land as structured, reviewable experience records. |
| AgentRR `[researched]` | Recording and summarizing agent trajectories supports replay for similar tasks. | `baseline replay select` should emit deterministic manifests and bundles tied to session identity. |
| AgentHER `[researched]` | Failed trajectories can be relabeled into useful training data when classification and confidence gates are explicit. | Replay ingest needs rubrics, confidence, judge identity, and human gates; no blind promotion. |
| Helicone replay / LangSmith trajectory evals / OpenAI agent evals `[researched]` | Production replay/eval systems rely on traces, graders, and full interaction context. | Because this repo has archived transcripts but not always full tool traces, v1 replay stays conservative. |
| W3C PROV-DM `[researched]` | Provenance models connect entities, activities, agents, derivations, and bundles. | Use a small provenance envelope for handoff records, replay manifests, and proposal sidecars. |

## 4. Architecture

```mermaid
flowchart LR
  Archive["archive/ + index.jsonl"] --> Schema["baseline/SCHEMA.md"]
  Schema --> Pages["baseline/projects/<slug>/README.md"]
  Schema --> Lint["baseline lint"]

  Handoffs["handoff artifacts"] --> HandoffMiner["baseline handoffs audit"]
  HandoffMiner --> HandoffIndex["baseline/handoffs/index.jsonl"]
  HandoffIndex --> Pages
  HandoffIndex --> Proposals["baseline/proposals/*.json"]

  Archive --> ReplaySelect["baseline replay select"]
  ReplaySelect --> Manifest["baseline/replay/manifests/*.jsonl"]
  Manifest --> Bundle["baseline/replay/bundles/*"]
  Bundle --> Replayer["external agent / panel"]
  Replayer --> ReplayIngest["baseline replay ingest"]
  ReplayIngest --> Proposals
  Proposals --> Candidates["baseline/candidates/"]
  Candidates --> Calibrate["baseline calibrate"]
  Calibrate --> Promote["baseline promote"]
  Promote --> Published["baseline/global/ + agent slices"]
  Lint -.-> Promote
```

### 4.1 Knowledge layer (#26)

Add `baseline/SCHEMA.md` as the contract for derived knowledge:

- Page types: global guardrail, project page, handoff index, replay manifest,
  proposal, candidate, calibration report.
- Ownership: human-owned prose, generated marker blocks, append-only ledgers.
- Provenance envelope: `source_entity`, `source_activity`, `source_agent`,
  `derived_from`, `evidence_ids`, `bundle_id`, `created_at`.
- Link rules: every generated block links to source evidence or a proposal id.
- Lint rules: schema conformance, broken links, orphan pages, stale generated
  blocks, duplicate claims, and contradiction candidates.

Project pages remain markdown, but generated regions are bounded:

```markdown
<!-- baseline:knowledge:start id="handoff-patterns" generated_by="baseline handoffs" -->
...
<!-- baseline:knowledge:end -->
```

The first pass should update only marker-owned blocks. Human prose remains
outside generated blocks.

### 4.2 Handoff mining (#23)

Handoff mining should be deterministic and auditable:

- Discover `SESSION_HANDOFF.md`, `session-handoff.md`, `MEMORY.md` start-here
  pointers, and agent-specific handoff sections in archived sessions.
- Normalize records into `baseline/handoffs/index.jsonl`.
- Render `baseline handoffs audit` as markdown for human review.
- Feed stable patterns into project pages and optional proposal JSON.

Suggested normalized handoff record:

```json
{
  "id": "handoff.agent-sessions.2026-07-07.codex",
  "project": "agent-sessions",
  "repo": "https://github.com/avidullu/agent-sessions",
  "agent": "codex",
  "source_path": "SESSION_HANDOFF.md",
  "source_kind": "repo-handoff",
  "observed_at": "2026-07-07T00:00:00Z",
  "open_threads": ["baseline knowledge + replay design"],
  "key_decisions": ["schema before replay"],
  "ramp_up_links": ["docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md"],
  "evidence_ids": ["archive:..."],
  "provenance": {
    "source_entity": "SESSION_HANDOFF.md",
    "source_activity": "handoff-mining",
    "source_agent": "codex",
    "derived_from": ["git:b6251f3"]
  }
}
```

### 4.3 Replay loop (#25)

Replay v1 is selection, packaging, and ingest - not local autonomous execution.

Proposed CLI:

- `baseline replay select --kind planning --limit 20`
  - deterministically picks sessions with enough self-contained context,
    excludes coding sessions, and writes a manifest.
- `baseline replay bundle --manifest <path>`
  - creates gitignored prompt/evidence packets with redaction and rubric files.
- `baseline replay ingest --result <path>`
  - validates an external replay result and converts improvements into structured
    proposals or candidate records.

Replay result minimum fields:

- `replay_of`: original archive/session id.
- `replayer`: agent, model family if known, and lineage different from original.
- `rubric_version`: versioned scoring prompt or panel rubric.
- `claim`: what the alternate run improves.
- `evidence`: original excerpt ids plus replay output ids.
- `confidence`: numeric or enum, with explanation.
- `recommended_action`: `proposal`, `watchlist`, or `reject`.

Daily automation should stay off until R1 and R2 gates pass:

- R1: replay selection precision is acceptable on manually reviewed manifests.
- R2: bundle redaction and provenance lint pass on sampled bundles.

## 5. Artifacts and contracts

| Path | Writer | Reader | Notes |
|---|---|---|---|
| `baseline/SCHEMA.md` | Human-reviewed docs PR | all baseline producers | Required before generated knowledge writes. |
| `baseline/projects/<slug>/README.md` | humans + marker-block upserts | agents and reviewers | Existing page shape is reused. |
| `baseline/handoffs/index.jsonl` | `baseline handoffs audit` | project page updater, proposal generator | Deterministic, append/upsert by source id. |
| `baseline/handoffs/audit.md` | `baseline handoffs audit` | human reviewer | Human-readable gaps and confidence. |
| `baseline/replay/manifests/*.jsonl` | `baseline replay select` | bundle command | Tracked if it contains no sensitive excerpts. |
| `baseline/replay/bundles/*` | `baseline replay bundle` | external replayer/panel | Gitignored by default; may contain session excerpts. |
| `baseline/replay/ledger.jsonl` | `baseline replay ingest` | calibration/eval | Append-only replay result history. |
| `baseline/proposals/*.json` | humans, handoff miner, replay ingest | `baseline ingest` | Extend schema or add sidecars for provenance fields. |

## 6. Honest limits - what this does NOT do

- No embeddings or semantic search in v1.
- No automatic promotion from handoff or replay findings.
- No free-form LLM rewrite of `baseline/projects/*`.
- No coding-session replay until snapshots or commit/worktree provenance exist.
- No replacement for the existing promote, publish, calibrate, and efficacy gates.

## 7. Deliverables & progress tracker

Legend: `Todo`, `In progress`, `Done`, `Blocked/gated`. One small PR per row.

| ID | Deliverable | Issue | Depends on | Gated? | Status | PR |
|---|---|---|---|---|---|---|
| K0 | Tracked design plan, docs index, and handoff pointer | #23/#25/#26 | - | No | Done | #45 |
| K1 | `baseline/SCHEMA.md` with page types, marker ownership, provenance, and lint contract | #26 | K0 | Yes | Todo | - |
| K2 | Project-page marker-block upsert helper for generated knowledge sections | #26 | K1 | Yes | Todo | - |
| K3 | `baseline lint` skeleton for schema, links, stale blocks, and orphan pages | #26 | K1,K2 | Yes | Todo | - |
| K4 | Handoff discovery and normalized `baseline/handoffs/index.jsonl` records | #23 | K1 | No | Todo | - |
| K5 | `baseline handoffs audit` markdown report and project-page feed | #23/#26 | K2,K4 | No | Todo | - |
| K6 | Handoff-derived proposal generation with evidence/provenance | #23 | K4,K5 | Yes | Todo | - |
| K7 | `baseline replay select` deterministic manifests, excluding coding sessions | #25 | K1 | No | Todo | - |
| K8 | `baseline replay bundle` gitignored packets with redaction and rubric files | #25 | K7 | Yes | Todo | - |
| K9 | `baseline replay ingest` validates external replay results into proposals/candidates | #25 | K6,K8 | Yes | Todo | - |
| K10 | Efficacy gates for schema lint, handoff precision, replay precision, and proposal acceptance | #23/#25/#26 | K3,K5,K9 | Yes | Todo | - |

## 8. Related issue triage

| Issue | Fold into this plan? | Reason |
|---|---|---|
| #19 - provenance trace logs | Yes, as substrate | Replay and handoff evidence need trace ids, but v1 can start with a lightweight provenance envelope. |
| #23 - mine handoffs | Yes, primary | First producer for the knowledge layer. |
| #25 - replay loop | Yes, primary | Second producer after schema, handoff mining, and redaction contracts. |
| #26 - wiki-style knowledge layer | Yes, primary | Foundation for both handoff mining and replay output. |
| #32 - backfill/regenerate | No, boundary | Useful for archive identity quality, but too broad for this project; keep it separate unless replay selection needs exact regenerated ids. |

## 9. Open questions - owner / external

1. Should `baseline/SCHEMA.md` be entirely hand-authored, or should commands also
   print machine-readable schema fragments from code?
2. What stale threshold should `baseline lint` use for generated project-page
   blocks: 30, 60, or 90 days?
3. Should replay manifests be tracked in Git by default if they include only ids
   and no excerpts?
4. Should replay ingest extend `proposal.schema.json`, or should provenance live
   in a sibling sidecar file to avoid breaking existing proposal writers?
5. Which session classes are allowed for replay v1 besides planning, writing,
   documentation, and research?

## 10. Definition of done

- [ ] `baseline/SCHEMA.md` exists and every new producer validates against it.
- [ ] Project pages have deterministic generated blocks with evidence links.
- [ ] `baseline lint` fails on broken generated links and stale/orphan blocks.
- [ ] `baseline handoffs audit` finds repo and archive handoff artifacts and
      writes normalized records.
- [ ] At least one handoff-derived finding reaches candidate/proposal review with
      provenance.
- [ ] `baseline replay select` and `baseline replay bundle` produce reviewed,
      redacted packets for self-contained non-coding sessions.
- [ ] `baseline replay ingest` accepts an external replay result and converts it
      into the existing proposal/candidate/calibration flow.
- [ ] Efficacy gates prove no auto-promotion and no silent page rewrites.

## 11. References

**Internal `[verified]`:** `docs/BASELINE_LOOP_CLOSURE.md`, `docs/CALIBRATION_EFFICACY.md`, `docs/COMPOSE_STACK.md`, `docs/BASELINE_WATCHLIST_TOMBSTONES.md`, `agent_sessions/baseline_agent.py`, `agent_sessions/baseline_ingest.py`, `baseline/proposals/proposal.schema.json`.

**Issues `[verified]`:** [#23](https://github.com/avidullu/agent-sessions/issues/23), [#25](https://github.com/avidullu/agent-sessions/issues/25), [#26](https://github.com/avidullu/agent-sessions/issues/26), related [#19](https://github.com/avidullu/agent-sessions/issues/19) and [#32](https://github.com/avidullu/agent-sessions/issues/32).

**External `[researched]`:** [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), [Reflexion](https://arxiv.org/abs/2303.11366), [Generative Agents](https://arxiv.org/abs/2304.03442), [Contextual Experience Replay](https://arxiv.org/abs/2506.06698), [AgentRR](https://arxiv.org/abs/2505.17716), [AgentHER](https://arxiv.org/abs/2603.21357), [Helicone session replay](https://docs.helicone.ai/guides/cookbooks/replay-session), [LangSmith trajectory evals](https://docs.langchain.com/langsmith/trajectory-evals), [OpenAI agent evals](https://developers.openai.com/api/docs/guides/agent-evals), [W3C PROV-DM](https://www.w3.org/TR/prov-dm/).

### Changelog

- 2026-07-07 - Opened draft PR #45 for the design tracker.
- 2026-07-07 - Created design tracker, indexed it in docs, updated the handoff pointer, and proposed execution sequence for #23, #25, and #26.
