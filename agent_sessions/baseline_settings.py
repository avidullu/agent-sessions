"""Baseline settings loading, scaffold templates, and artifact resolution."""

from __future__ import annotations

from pathlib import Path

from .baseline_types import BaselineSettings, Pilot
from .config import ArchiveConfig, read_toml, repo_path


BASELINE_CONFIG = Path("config/baseline.toml")
BASELINE_ROOT = Path("baseline")
PROJECT_README_PLACEHOLDER = "Project-specific promoted baseline notes for `{slug}` will land here."


def load_baseline_settings(config: ArchiveConfig) -> BaselineSettings:
    path = config.repo_root / BASELINE_CONFIG
    data = read_toml(path) if path.exists() else {}
    baseline = data.get("baseline", {})
    root = repo_path(config.repo_root, baseline.get("root", str(BASELINE_ROOT)))
    candidates_dir = repo_path(config.repo_root, baseline.get("candidates_dir", str(BASELINE_ROOT / "candidates")))
    metacognition_dir = repo_path(config.repo_root, baseline.get("metacognition_dir", str(BASELINE_ROOT / "metacognition")))
    ledger_path = repo_path(
        config.repo_root,
        baseline.get("ledger_path", str(BASELINE_ROOT / "metacognition" / "prediction-ledger.jsonl")),
    )
    feedback_example = repo_path(
        config.repo_root,
        baseline.get("feedback_example", str(BASELINE_ROOT / "calibration" / "feedback.example.toml")),
    )
    pilots = tuple(
        Pilot(
            slug=item["slug"],
            kind=item.get("kind", "repo"),
            aliases=tuple(item.get("aliases", [])),
            notes=item.get("notes", ""),
        )
        for item in data.get("pilots", [])
    )
    return BaselineSettings(
        root=root,
        candidates_dir=candidates_dir,
        metacognition_dir=metacognition_dir,
        ledger_path=ledger_path,
        feedback_example=feedback_example,
        pilots=pilots,
    )


def load_feedback(config: ArchiveConfig, feedback: Path | None) -> dict[str, dict[str, str]]:
    if feedback is None:
        default = config.repo_root / "baseline" / "calibration" / "feedback.toml"
        feedback = default if default.exists() else None
    if feedback is None:
        return {}
    if not feedback.is_absolute():
        feedback = config.repo_root / feedback
    if not feedback.exists():
        raise SystemExit(f"Feedback file does not exist: {feedback}")
    data = read_toml(feedback)
    raw = data.get("feedback", {})
    return {str(key): dict(value) for key, value in raw.items() if isinstance(value, dict)}


def resolve_prediction_sidecar(settings: BaselineSettings, predictions: Path | None) -> Path:
    if predictions is not None:
        if not predictions.is_absolute():
            predictions = settings.root.parent / predictions
        if not predictions.exists():
            raise SystemExit(f"Prediction sidecar does not exist: {predictions}")
        return predictions
    sidecars = sorted(settings.candidates_dir.glob("*.predictions.json"), key=lambda path: path.stat().st_mtime)
    if not sidecars:
        raise SystemExit("No prediction sidecar found. Run `baseline suggest` first.")
    return sidecars[-1]


def baseline_files(settings: BaselineSettings) -> dict[Path, str]:
    files = {
        settings.root / "README.md": baseline_readme(),
        settings.root / "SCHEMA.md": baseline_schema(),
        settings.root / "candidates" / "README.md": candidates_readme(),
        settings.root / "global" / "engineering-guardrails.md": "# Engineering Guardrails\n\nPromoted guidance will land here.\n",
        settings.root / "global" / "repo-workflows.md": "# Repo Workflows\n\nPromoted repo workflow guidance will land here.\n",
        settings.root / "global" / "regression-frameworks.md": "# Regression Frameworks\n\nPromoted testing guidance will land here.\n",
        settings.root / "global" / "prompt-patterns.md": "# Prompt Patterns\n\nPromoted prompt guidance will land here.\n",
        settings.root / "agents" / "codex" / "README.md": agent_readme("Codex", "AGENTS.generated.md"),
        settings.root / "agents" / "claude" / "README.md": agent_readme("Claude", "CLAUDE.generated.md"),
        settings.root / "agents" / "vscode" / "README.md": agent_readme("VS Code", "copilot-instructions.generated.md"),
        settings.metacognition_dir / "README.md": metacognition_readme(),
        settings.feedback_example: feedback_example(),
    }
    for pilot in settings.pilots:
        files[settings.root / "projects" / pilot.slug / "README.md"] = project_readme(pilot.slug)
    return files


def baseline_readme() -> str:
    return """# Engineering Baseline

This directory holds reviewed engineering guardrails, project memory, and
agent-specific generated views derived from archived sessions and repo evidence.

`SCHEMA.md` is the contract for derived baseline artifacts, marker ownership,
trace fields, and validator behavior. Commands that write generated knowledge
or replay/handoff outputs should follow that schema before adding new artifact
types.

Candidate files are suggestions. Promoted files are reviewed baseline guidance.
Generated agent files should stay separate from hand-written project instruction
files until their output proves useful.
"""


def baseline_schema() -> str:
    return """# Baseline Derived Layer Schema

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
| Proposal inputs | `baseline/proposals/*.json` | human or bounded producer | Reviewable proposal drafts ingested into candidates; K7 handoff proposals are deterministic review inputs with structured trace. |
| Handoff audit | `baseline/handoffs/audit.md` | generated report | K2 audit output only; no pages, proposals, or index writes. |
| Handoff index | `baseline/handoffs/index.jsonl` | generated records | K6 persistent normalized handoff records; project-page feeds are marker blocks on configured or existing project pages only. |
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
- Handoff audit is report-only. Persistent handoff indexing writes
  `baseline/handoffs/index.jsonl` for all discovered records, while project-page
  feeds update only configured or already-scaffolded project pages.
- Generated handoff proposals may overwrite only proposal files already marked
  with `generated_by = "baseline handoffs proposals"`; hand-written proposals
  are never replaced by that producer.
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
- Producers should preserve an existing `generated_at` value when a marker
  block's substantive generated content is unchanged, so periodic runs converge
  to quiet diffs.
- Metadata such as `generated_by`, `generated_at`, and `proposal_id` belongs in
  the block body or in structured sidecars unless the shared parser changes.

## 5. Trace Fields

Generated proposals, candidate sidecars, handoff records, replay records, and
future project-page blocks should use this #19-aligned trace vocabulary when a
field is available:

| Field | Meaning |
|---|---|
| `source` | Archive source or producer name, for example `codex`, `baseline handoffs audit`, or `baseline handoffs proposals`. |
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

Structured proposal fields:

- `source_kind` is optional for human-authored proposals; replay and handoff
  producers should use `replay`, `handoff`, or `repo-handoff`.
- K7 handoff-derived proposal files use
  `generated_by = "baseline handoffs proposals"` and `source_kind =
  "repo-handoff"`; they are review inputs, not promotion decisions.
- `replay_of`, when present, is the original archive session id and must resolve
  against `archive/index.jsonl`.

Resolution rules:

- `markdown_path` is repo-relative and uses forward slashes.
- `session_id` and `markdown_path` references from replay or handoff producers
  must resolve against `archive/index.jsonl` before candidate creation.
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
differences, spaces, URL-encoded drive paths, hyphen-encoded Claude project
paths, and duplicate basenames so two unknown projects do not collapse into one
page or handoff record. Configured pilot aliases may intentionally collapse
multiple raw paths into one canonical project slug.

## 7. Validation Contract

`baseline lint` is the schema-wide validator for deterministic checks that can
run before generated project-page feeds exist. It returns non-zero for errors;
warnings are review signals that later K rows can make stricter as producers
start writing richer artifacts.

Required validator behavior:

- Reject malformed marker pairs and duplicate generated block ids in a page.
- Fail generated writes that would alter human-owned prose.
- Fail on broken links inside generated marker blocks.
- Warn on project pages that have neither inbound baseline links nor generated
  blocks; K6 `handoffs.index` feeds satisfy the generated-block side of that
  check.
- Warn on stale generated blocks by age and malformed generated dates; later
  producers should add source-record freshness checks.
- Warn on explicit contradiction markers; deeper P6 duplicate/contradiction
  analysis can harden this rule.
- Reject replay or handoff proposal ingest when required trace references do
  not resolve.
- Refuse generated handoff proposal overwrites unless the target is already
  owned by the same handoff proposal producer.
- Fail replay bundle writes when redaction detects high-confidence secrets.

## 8. Non-Goals

- No embeddings or semantic search in v1.
- No automatic promotion from handoff, replay, or candidate artifacts.
- No free-form LLM rewrite of project pages.
- No coding-session replay until workspace snapshots or commit/worktree
  provenance exists.

## 9. Changelog

- 2026-07-07: Added K11 `baseline replay ingest`: validates external replay results, emits `replay.*` proposals that clear the K5 gate, and appends the append-only `baseline/replay/ledger.jsonl`.
- 2026-07-07: Added K10 `baseline replay bundle`: gitignored replay packets (redacted task + deliverable + rubric + per-bundle redaction report) written only for sessions that pass the fail-closed redaction gate.
- 2026-07-07: Added K9 replay redaction v0: deterministic fail-closed secret scanner and `redaction-report.json` (values never recorded); gitignored replay egress.
- 2026-07-07: Added K8 `baseline replay select` deterministic, excerpt-free replay manifest (`baseline/replay/manifest.jsonl`) excluding coding sessions.
- 2026-07-07: Added K7 generated handoff proposal ownership rules and stable project-page generated dates for unchanged feeds.
- 2026-07-07: Added K6 persistent handoff index records and configured project-page `handoffs.index` feeds.
- 2026-07-07: Added K5 proposal trace propagation and ingest reference validation.
- 2026-07-07: Added K4 `baseline lint` severity model and first validator scope.
- 2026-07-07: Added K3 project-page marker-block helper contract.
- 2026-07-07: Initial schema for K1 of the baseline knowledge/replay tracker.
"""


def candidates_readme() -> str:
    return """# Baseline Candidates

Candidate files are generated suggestions with provenance, confidence, risk, and
promotion checkboxes. Review these in PRs before promoting anything into the
global or project baseline.
"""


def agent_readme(agent_name: str, generated_name: str) -> str:
    return f"""# {agent_name} Baseline View

Generated {agent_name} instructions will land in `{generated_name}` later. Keep
this separate from hand-written project instructions until the publisher is
trusted.
"""


def project_readme(slug: str) -> str:
    return f"""# {slug}

{PROJECT_README_PLACEHOLDER.format(slug=slug)}
"""


def feedback_example() -> str:
    return """# Copy to feedback.toml and mark predictions after reviewing a candidate file.

[feedback."profile.multi-agent-builder"]
verdict = "accept"
note = "This matches the user's actual working style."

[feedback."profile.local-first-private-compute"]
verdict = "edit"
note = "Keep the local-first point, but mention that cloud APIs are acceptable when explicitly authorized."

[feedback."profile.business-productivity-engineer"]
verdict = "reject"
note = "Example of a rejected hypothesis."
"""


def metacognition_readme() -> str:
    return """# Metacognition

This folder holds machine-readable prediction history and calibration summaries.
The loop is: generate predictions from local evidence, collect feedback, compare
error, and make the next candidate report sharper.
"""
