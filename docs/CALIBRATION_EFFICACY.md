# Calibration Efficacy

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-07-22`
> Efficacy gates E1–E6 for measuring whether the baseline loop is learning.

How to measure whether `agent-sessions` is working — not just archiving sessions,
but learning the user's engineering patterns and closing the baseline loop.

Machine-readable metrics live in `baseline/calibration/efficacy.toml`. Update
status there after each review cycle.

## Why a calibration anchor?

Archive analysis identified a **repeatable standard** the user already applies in
production repos:

| Anchor | Location | Archive evidence |
|--------|----------|------------------|
| Tracked project doc template | `badminton-highlight-indexer/docs/PROJECT_DOC_TEMPLATE.md` | 237 sessions mention `PROJECT_DOC_TEMPLATE` |
| Session handoff + ramp-up kit | `SESSION_HANDOFF.md`, `session-handoff` skills | 943 sessions mention handoff/ramp-up |
| §7 progress tracker discipline | Precedents in engine + khelsutra repos | Widespread in archived Claude/Codex sessions |

The tool proves efficacy when it can **detect → propose → promote → apply** this
pattern — starting with dogfooding on `docs/archives/BASELINE_LOOP_CLOSURE.md` in this repo.

## Efficacy gates

| ID | Gate | Pass condition | Measures |
|----|------|----------------|----------|
| E1 | **Detect** | `baseline suggest` emits `guardrail.tracked-project-docs` with evidence citing archive hits | Tool finds user's template pattern without being told the path |
| E2 | **Anchor** | `config/baseline.toml` `calibration_anchors` lists `badminton-highlight-indexer` template | Explicit link between archive inference and known ground truth |
| E3 | **Dogfood** | `docs/archives/BASELINE_LOOP_CLOSURE.md` exists as a filled tracked project doc | Tool's iteration uses the user's own template |
| E4 | **Promote** | ≥1 rule in `baseline/global/` is non-placeholder promoted text | Loop produces durable policy, not just candidates |
| E5 | **Publish** | `baseline/agents/claude/CLAUDE.generated.md` (or codex equivalent) exists | Agents can consume output |
| E6 | **Calibrate** | Second `baseline suggest` after `feedback.toml` shows adjusted confidence or suppressed rejected IDs | Feedback changes behavior |

## Review cadence

1. Run `baseline suggest` and check E1.
2. Copy `feedback.example.toml` → `feedback.toml`; mark `guardrail.tracked-project-docs` and top guardrails.
3. Run `baseline calibrate --feedback baseline/calibration/feedback.toml`.
4. After promote/publish land, re-run suggest and update `efficacy.toml` statuses.
5. When E1–E6 pass, mark `docs/archives/BASELINE_LOOP_CLOSURE.md` §7 P9 ☑.

## Commands

```powershell
python .\tools\agent_archive.py baseline suggest
python .\tools\agent_archive.py baseline calibrate --feedback baseline\calibration\feedback.toml
python .\tools\agent_archive.py baseline bundle --focus PROJECT_DOC_TEMPLATE --focus badminton-highlight-indexer
```

## Related

- Tracked project: `docs/archives/BASELINE_LOOP_CLOSURE.md`
- Template: `docs/PROJECT_DOC_TEMPLATE.md`
- Metrics file: `baseline/calibration/efficacy.toml`
- Compose scope: `docs/COMPOSE_STACK.md`