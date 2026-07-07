# Engineering Baseline

For current planning, pilot scope, and PR-sized work items, see
[BASELINE_PLANNING.md](BASELINE_PLANNING.md).

## Context

The archive captures useful evidence: which repositories show up repeatedly,
which guardrails prevent regressions, which prompts lead to strong outcomes, and
which workflow mistakes cost time. That information should become a local,
reviewable engineering baseline rather than staying buried in transcripts.

## Decision

Keep raw session export and baseline extraction as separate stages:

1. Archive sessions to durable Markdown/PDF and an index.
2. Derive candidate lessons from archived sessions.
3. Review and promote selected lessons into a local baseline.
4. Publish baseline slices into agent-specific files for Codex, Claude, and VS
   Code-supported workflows.

This keeps the archive faithful to source data while allowing the baseline to be
curated, opinionated, and safe to inject into future projects.

## Proposed Layout

```text
baseline/
  SCHEMA.md
  global/
    engineering-guardrails.md
    prompt-patterns.md
    repo-workflows.md
  handoffs/
    audit.md
  agents/
    codex/AGENTS.generated.md
    claude/CLAUDE.generated.md
    vscode/copilot-instructions.generated.md
  projects/
    <repo-slug>/
      decisions.md
      pitfalls.md
      test-and-release.md
  candidates/
    YYYY-MM-DD-extraction.md
```

## Extraction Shape

- Read `archive/index.jsonl` and selected Markdown transcripts.
- Identify repeated repo names, commands, file conventions, failure modes,
  review findings, test gates, and user preferences.
- Write candidate notes with provenance links back to archive files.
- Require an explicit promote step before updating baseline files.

## Agent Hooks

- Codex: project `AGENTS.md` can include or mirror the generated Codex baseline
  section.
- Claude: project `CLAUDE.md` can include or mirror the generated Claude
  baseline section.
- VS Code: a VS Code adapter can publish a generated instruction file once the
  chosen local instruction target is validated on each machine.
- External/peer agents: `baseline bundle` can produce a bounded local evidence
  packet plus a proposal prompt for any explicitly authorized agent. Generated
  evidence packets are ignored by Git by default.
- Handoff mining: `baseline handoffs audit` writes a report-only coverage and
  freshness audit at `baseline/handoffs/audit.md`; persistent handoff indexes
  and project/proposal feeds are later gated work.

## Guardrails

- Never promote secrets, credentials, private file contents, or one-off debug
  noise into the baseline.
- Keep provenance for every promoted rule or pattern.
- Prefer short, stable guidance over transcript summaries.
- Separate global guidance from project-specific guidance.
- Preserve manual sections in project instruction files; generated sections
  should have clear begin/end markers.
- Let the periodic job propose baseline changes, but keep promotion reviewable.

## First Useful Version

The first version can be simple and deterministic:

- Scan archive metadata for repo/project names and agent sources.
- Extract headings and repeated commands from Markdown transcripts.
- Produce `baseline/candidates/<date>-extraction.md`.
- Add a manual `promote-baseline` command later, after the candidate format feels
  useful.

It should also make explicit metacognitive predictions about the user and the
work style, then invite calibration feedback. The loop is: predict from local
evidence, ask what was right or wrong, record feedback, and make the next report
less vague. Prediction sidecars and a ledger make that loop machine-readable so
future runs can compare what the tool guessed against what the user confirmed.
