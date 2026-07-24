# Engineering Baseline

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-07-22`
> Baseline architecture: promote/publish/calibrate pipeline and artifact layout.

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
    index.jsonl
  agents/
    codex/AGENTS.generated.md
    claude/CLAUDE.generated.md
    vscode/copilot-instructions.generated.md
  projects/
    <repo-slug>/
      README.md
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
  freshness audit at `baseline/handoffs/audit.md`; `baseline handoffs index`
  writes persistent records to `baseline/handoffs/index.jsonl` and marker-owned
  `handoffs.index` feeds only on configured or already-scaffolded project pages.
  `baseline handoffs proposals` turns that index into deterministic proposal
  JSON files under `baseline/proposals/`, refuses to overwrite hand-written
  proposals, and relies on `baseline ingest --dry-run` for reference validation.
- Project pages: generated sections in `baseline/projects/<slug>/README.md`
  should use `render_project_page_block()` and
  `upsert_project_page_content()` so the shipped `baseline:begin/end` marker
  parser preserves hand-written prose. Only the exact scaffold placeholder line
  is removed; edited placeholder-like prose is preserved as human-owned content.
- Baseline lint: `baseline lint` is read-only by default and reports schema,
  marker, generated-link, stale-block, malformed generated-date, orphan-page,
  and explicit contradiction findings. Errors fail the command; warnings surface
  review signals while later producers are still gated.
- Replay selection: `baseline replay select` scores archived sessions for
  replayability and writes a deterministic `baseline/replay/manifest.jsonl` of
  selected and near-miss candidates with exclusion reasons and no transcript
  excerpts. Coding sessions are excluded in v1; redaction and bundle egress are
  later gated work.
- Replay redaction: `baseline replay redact` runs a deterministic, fail-closed
  secret scan over the selected sessions and writes a valueless
  `redaction-report.json` under the gitignored `baseline/replay/bundles/`.
  High-confidence secrets block the egress gate (non-zero exit); low-risk emails
  and private paths are placeholdered. Secret values are never recorded.
- Replay bundles: `baseline replay bundle` writes one gitignored packet per
  selected session (redacted task prompt + original deliverable + comparison
  rubric + per-bundle redaction report). Sessions whose egress content trips the
  fail-closed scanner are skipped with a report and never written. Bundles stay
  under the gitignored `baseline/replay/bundles/` and are handed to an external
  replayer/judge out of band.
- Replay ingest: `baseline replay ingest` validates an external replay result
  (its `replay_of`/trace references must resolve against `archive/index.jsonl`),
  appends it to the append-only `baseline/replay/ledger.jsonl`, and — when the
  judge recommends it — emits a `replay.*` proposal that flows through the same
  human-gated `baseline ingest` -> candidate -> promote pipeline. Nothing is
  auto-promoted.
- Efficacy gates: `baseline eval` reports E1-E6 plus the K12 W/H/R gates
  (schema/marker/link, handoff precision/freshness, replay R1-R5) and a
  `G-no-autopromote` governance gate. Gates whose prerequisites do not exist yet
  (e.g. no external replay result ingested) report `gated` rather than passing or
  failing.

## Guardrails

- Never promote secrets, credentials, private file contents, or one-off debug
  noise into the baseline.
- Keep provenance for every promoted rule or pattern.
- Prefer short, stable guidance over transcript summaries.
- Separate global guidance from project-specific guidance.
- Preserve manual sections in project instruction files; generated sections
  should have clear begin/end markers.
- Run `baseline lint --dry-run` before merging generated baseline producers.
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
