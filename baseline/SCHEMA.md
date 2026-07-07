# Baseline Derived Layer Schema

> **Status:** `v1 draft`.
> **Owner:** human-reviewed docs PRs.
> **Scope:** files under `baseline/` that are derived from archives, repo
> handoffs, replay packets, proposals, candidates, calibration, or promotion.

## 1. Purpose

The baseline layer converts immutable archive and repo evidence into reviewed,
versioned guidance. This schema defines the artifact types, ownership rules,
marker grammar, provenance fields, and validator contracts that producers must
follow before they write generated knowledge.

The schema is intentionally markdown-first. It is the human-readable contract;
command-specific validators and future `baseline lint` checks enforce it for
new generated producers. `baseline/proposals/proposal.schema.json` remains an
illustrative proposal example until proposal validation is formalized in code.

## 2. Artifact Types

| Type | Path | Ownership | Notes |
|---|---|---|---|
| Baseline root | `baseline/README.md`, `baseline/SCHEMA.md` | human | Entry point and contract. |
| Global guardrails | `baseline/global/*.md` | human prose + marker blocks | Reviewed guidance promoted from candidates. |
| Agent views | `baseline/agents/*/*.generated.md` | generated | Derived views for specific agents; do not overwrite hand-authored repo instructions. |
| Project pages | `baseline/projects/<slug>/README.md` | human prose + marker blocks | Durable project knowledge and generated sections. |
| Candidate reports | `baseline/candidates/*.md` | generated, reviewed by humans | Human-readable reports with sidecars. |
| Candidate sidecars | `baseline/candidates/*.predictions.json` | generated | Structured prediction payloads and trace data. |
| Proposal inputs | `baseline/proposals/*.json` | human or bounded producer | Reviewable proposal drafts ingested into candidates. |
| Handoff audit | `baseline/handoffs/audit.md` | generated report | K2 audit output only; no pages, proposals, or index writes. |
| Handoff index | `baseline/handoffs/index.jsonl` | generated records | K6 persistent normalized handoff records. |
| Replay manifest | `baseline/replay/manifest.jsonl` | generated records | Deterministic selected session refs and exclusion reasons, no excerpts. |
| Replay bundles | `baseline/replay/bundles/*` | generated egress | Gitignored packets that may contain excerpts after redaction preflight. |
| Replay ledger | `baseline/replay/ledger.jsonl` | append-only generated records | Replay-result history after validated ingest. |
| Prediction/feedback ledgers | `baseline/metacognition/*.jsonl` | append-only generated records | Prediction and feedback history. |
| Calibration inputs/reports | `baseline/calibration/*.toml`, `baseline/calibration/*.md` | human + generated reports | Efficacy gates and calibration feedback. |

## 3. Ownership Rules

- Raw archive data remains immutable input. Baseline producers derive from it;
  they do not rewrite it.
- Human-authored prose outside generated markers is preserved.
- Generated markdown updates are limited to marker-owned blocks or explicitly
  generated files.
- Append-only ledgers are rewritten only through atomic upsert semantics that
  preserve unrelated runs.
- Candidate and proposal artifacts are review inputs. They do not become policy
  until promotion writes reviewed guidance.
- Handoff audit is report-only. Persistent handoff indexing and project-page
  feeds are separate K6 behavior.
- Replay bundle egress is blocked unless deterministic redaction passes and
  bundle paths are gitignored.

## 4. Marker Grammar

Generated markdown blocks use the existing promotion marker grammar:

```markdown
<!-- baseline:begin id="stable.block.id" -->
Generated content.
<!-- baseline:end id="stable.block.id" -->
```

Rules:

- Begin and end markers must use the same `id`.
- IDs are stable dotted or dashed identifiers scoped to the target page.
- Producers must preserve all content outside owned marker blocks.
- Producers must not introduce a second marker family for knowledge pages.
- Project-page producers should render sections with `render_project_page_block()`
  and write them through `upsert_project_page_content()`, which reuses the same
  marker parser/upsert path as promoted guardrails.
- Project-page upserts may remove the scaffold placeholder only when the line
  exactly matches the known placeholder text; edited placeholder-like prose is
  human-owned content.
- Metadata such as `generated_by`, `generated_at`, and `proposal_id` belongs in
  the block body or in structured sidecars unless the shared parser changes.

## 5. Trace Fields

Generated proposals, candidate sidecars, handoff records, replay records, and
future project-page blocks should use this #19-aligned trace vocabulary when a
field is available:

| Field | Meaning |
|---|---|
| `source` | Archive source or producer name, for example `codex` or `baseline handoffs audit`. |
| `source_file` | Original raw source file or repo handoff path when known. |
| `markdown_path` | Repo-relative markdown artifact, usually under `archive/`. |
| `session_id` | Session identifier from record metadata when available. |
| `timestamp` | Observation or source timestamp in ISO 8601 form when available. |
| `project_slug` | Deterministic project identifier used under `baseline/projects/`. |
| `repo` | Repository URL or canonical repo id when known. |
| `evidence_anchor` | Heading, marker id, excerpt id, or other stable local anchor. |
| `evidence_excerpt` | Short evidence quote or summary, after redaction rules. |
| `transform` | Deterministic transform that produced the record. |
| `bundle_id` | Replay or agent bundle identifier when the evidence came from a bundle. |
| `calibration_effect` | Optional feedback/calibration note, for example accepted, edited, or rejected. |

Resolution rules:

- `markdown_path` is repo-relative and uses forward slashes.
- `session_id` and `markdown_path` references from replay or handoff producers
  must resolve against `archive/index.jsonl` before candidate creation once K5
  lands.
- Hand-written proposals may continue to use free-text `evidence` lists, but
  external replay and handoff producers must include structured trace records
  before ingest promotes them into candidates.
- Trace records should be copied forward into prediction sidecars so later
  calibration and promotion can cite their derivation.

## 6. Project Identity

Project page paths use `baseline/projects/<slug>/README.md`.

Slug derivation priority:

1. Configured `config/baseline.toml` pilot slugs and aliases.
2. Canonical repository URL when known.
3. Decoded `metadata.project` or `metadata.cwd` basename.
4. A stable disambiguator when names collide.

K6/K8 implementations must include fixture coverage for Windows paths with case
differences, spaces, URL-encoded drive paths, and duplicate basenames so two
projects do not collapse into one page or handoff record.

## 7. Validation Contract

`baseline lint` is the schema-wide validator for deterministic checks that can
run before generated project-page feeds exist. It returns non-zero for errors;
warnings are review signals that later K rows can make stricter as producers
start writing richer artifacts.

Required validator behavior:

- Reject malformed marker pairs and duplicate generated block ids in a page.
- Fail generated writes that would alter human-owned prose.
- Fail on broken links inside generated marker blocks.
- Warn on orphan project pages until K6 creates generated project-page feeds.
- Warn on stale generated blocks by age; later producers should add source-record
  freshness checks.
- Warn on explicit contradiction markers; deeper P6 duplicate/contradiction
  analysis can harden this rule.
- Reject replay or handoff proposal ingest when required trace references do
  not resolve.
- Fail replay bundle writes when redaction detects high-confidence secrets.

## 8. Non-Goals

- No embeddings or semantic search in v1.
- No automatic promotion from handoff, replay, or candidate artifacts.
- No free-form LLM rewrite of project pages.
- No coding-session replay until workspace snapshots or commit/worktree
  provenance exists.

## 9. Changelog

- 2026-07-07: Added K4 `baseline lint` severity model and first validator scope.
- 2026-07-07: Added K3 project-page marker-block helper contract.
- 2026-07-07: Initial schema for K1 of the baseline knowledge/replay tracker.
