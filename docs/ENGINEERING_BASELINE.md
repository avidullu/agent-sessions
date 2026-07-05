# Engineering Baseline

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
  global/
    engineering-guardrails.md
    prompt-patterns.md
    repo-workflows.md
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
