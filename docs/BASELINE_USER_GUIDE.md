# Review lessons from your sessions

Baseline commands turn archive evidence into candidate guidance. A suggestion
is not an instruction, and accepting a prediction does not install anything in
another agent's memory. This guide covers the existing local baseline workflow,
not the unshipped external-memory promote gate in [the product boundary](XDSYNC_BOUNDARY.md).

## Start in your private archive workspace

Use hub 0.3.0 or newer and the workspace from [Getting Started](GETTING_STARTED.md).
Review source paths and export only sessions you intend to inspect. No product
checkout is required for these commands.

```sh
agent-archive status
agent-archive baseline scaffold --dry-run
agent-archive baseline scaffold
agent-archive baseline suggest --dry-run
agent-archive baseline suggest --output baseline/candidates/review.md
```

Scaffolding creates missing local templates and preserves existing files.
Suggestion writes a candidate report, a matching `review.predictions.json`
sidecar, and prediction-ledger entries. Inspect the report and its evidence.
An empty or sparse archive may not yield useful candidates; do not manufacture
acceptances to make the workflow look successful.

## Give feedback on an exact candidate run

Suppose the report contains `guardrail.verified-regression-gates` and its evidence
really supports running a focused regression check before claiming a fix. Create
`baseline/calibration/feedback.toml` with only the IDs you actually reviewed:

```toml
[feedback."guardrail.verified-regression-gates"]
verdict = "accept"
note = "Reviewed the cited synthetic example; this is appropriate for this project."
```

This ID is illustrative: use one from your own sidecar. `reject` records an
unsuitable suggestion; `edit` records that revision is needed. An edit note does
not itself rewrite the proposed rule. Avoid blindly copying the example feedback
file: it contains illustrative acceptances, not your approval.

```sh
agent-archive baseline calibrate --feedback baseline/calibration/feedback.toml --predictions baseline/candidates/review.predictions.json --dry-run
agent-archive baseline promote --feedback baseline/calibration/feedback.toml --predictions baseline/candidates/review.predictions.json --id guardrail.verified-regression-gates --dry-run
```

Always name the sidecar during review. Omitting `--predictions` selects the most
recent sidecar by modification time, which may not be the run you inspected.
Only accepted `guardrail.*` predictions are eligible for this promotion command;
profile hypotheses, rejected items and items marked `edit` are not promoted.

## Promote locally, then inspect the generated view

After reviewing the dry run, repeat the same `baseline promote` command without
`--dry-run`. It writes owned marker blocks under `baseline/global/`, including
the candidate ID, source run and review note. It preserves surrounding prose.

```sh
agent-archive baseline publish --agent codex --dry-run
agent-archive baseline publish --agent codex
agent-archive baseline lint --dry-run
```

The Codex view is `baseline/agents/codex/AGENTS.generated.md`; Claude and VS Code
have separate generated views selectable with `--agent`. Publishing here means
writing local derived files. It does **not** upload to a service, install a hook,
or overwrite your project's `AGENTS.md` or `CLAUDE.md`.

Review the resulting file before choosing how an agent will consult it. Keep
hand-authored policy authoritative. Do not advertise this workflow as automatic
self-learning or as the future owner-attested external-memory bridge.

## When to calibrate

Run calibration after reviewing suggestions and again when later sessions show
whether accepted guidance helped. Record uncertainty and rejections as well as
successes. `baseline eval --dry-run` checks the repository's E1–E6 loop criteria;
it is not proof that a new personal archive has improved agent performance.

Keep feedback, candidates, evidence and generated views private unless you
explicitly choose otherwise. They can contain project details even when no raw
transcript is copied. For deeper mechanics, see [baseline architecture](ENGINEERING_BASELINE.md),
[efficacy criteria](CALIBRATION_EFFICACY.md), and the [rules implementation plan](RULES_EXTRACTION_AND_PUBLISH_PLAN.md).
