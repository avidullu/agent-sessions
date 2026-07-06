# pr-review-loop (Claude Code plugin)

A self-pacing PR reviewer. It sleeps ~15 minutes, wakes to review open PRs
(validating locally by running the tests), posts an `LGTM` comment when
satisfied so the **author** can merge, and auto-stops its own sleep-wake alarm
after N consecutive empty polls.

Ships one skill: `/pr-review-loop:start`.

## Install

This repo (`avidullu/agent-sessions`) hosts a marketplace named
`agent-sessions-tools`. From any Claude Code session:

```shell
/plugin marketplace add avidullu/agent-sessions
/plugin install pr-review-loop@agent-sessions-tools
```

Then start the reviewer in the target repo's session:

```shell
/pr-review-loop:start
```

…or just ask in natural language: *"be the designated reviewer for PRs on this
repo — LGTM once you validate them, stop after 3 empty polls."* The skill is
model-invoked, so it also triggers when you ask to watch/review/babysit PRs.

## Parameters

Parsed from your request; sensible defaults otherwise: `repo`, `filter` (tracker
/ label / branch prefix / title substring), `cadence_min` (default 15),
`idle_stop` (default 3), `worktree`.

## Behavior notes

- Reviews for correctness **and** side effects; validates by running the repo's
  tests/lint locally, not just reading the diff.
- Posts LGTM as a **comment** (works even when the acting account can't formally
  self-approve); the **author merges** — the reviewer never does.
- The idle counter rides in the wake-up message, so the loop is stateless across
  firings and survives context compaction.
- New-PR discovery latency ≈ `cadence_min`; already-subscribed PRs get real-time
  push for new commits/comments.

## Local development

```shell
claude --plugin-dir ./plugins/pr-review-loop
```
