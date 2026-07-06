---
name: pr-review-loop
description: >-
  Stand up a self-pacing PR reviewer that sleeps ~15 min, wakes to review open
  PRs (validate locally, post LGTM as a comment or actionable feedback, let the
  author merge), and auto-stops its own sleep-wake alarm after N consecutive
  empty polls. Use when the user asks to "watch"/"review"/"babysit" incoming PRs
  on a repo or a tracker as the designated reviewer across a session or siblings.
  Reusable: parameterize repo, PR filter, cadence, and idle-stop threshold.
---

# PR Review Loop

A reusable reviewer loop. It polls a repo for open PRs on a self-pacing alarm,
reviews each one thoroughly (correctness **and** side effects, validated by
running the tests locally), posts an **LGTM comment** when satisfied — the PR
**author merges**, the reviewer never does — and **shuts its own alarm off**
after a configurable number of consecutive empty polls so it never idles
forever.

## When to use

- The user says "become the reviewer", "watch/review/babysit incoming PRs",
  "LGTM PRs once you validate them", or points you at a tracker whose PRs a
  sibling agent will author.
- You want this to run unattended across wake-ups, on this session or a sibling.

## Parameters (parse from the user's request; use defaults otherwise)

| Param | Default | Meaning |
|-------|---------|---------|
| `repo` | the session's in-scope repo (`owner/name`) | Repo to watch. |
| `filter` | all open PRs | Which PRs count — e.g. a tracker (TD1–TD15), a label, a branch prefix, a title substring. State it explicitly in the alarm message. |
| `cadence_min` | `15` | Minutes to sleep between polls (self-re-arm; the recurring-cron floor of 60 min does not apply to one-shot wake-ups). |
| `idle_stop` | `3` | Stop the alarm after this many **consecutive** polls that found no PR needing review. |
| `worktree` | `/home/user/agent-sessions` (or the session repo path) | Where to check out branches for local validation. |

## Setup (run once when invoked)

1. Confirm the acting GitHub identity (`get_me`). If it is the **same account
   that authors the PRs**, note that GitHub blocks self-approval — post LGTMs as
   **comments** (`add_issue_comment`), not formal approvals.
2. Do an immediate first poll (the review procedure below) so the user sees it
   working, then arm the alarm for the next cycle.
3. Arm the alarm with `send_later` (or `ScheduleWakeup` in a `/loop`), setting
   `delay_minutes = cadence_min` and passing the **alarm message** below. The
   message must carry the full review procedure and the current idle counter, so
   each firing is self-contained and survives context summarization.

## Alarm message template (pass verbatim to send_later each cycle)

> `[pr-review-loop | repo=<repo> | filter=<filter> | cadence=<cadence_min>m | idle_stop=<idle_stop> | idle_streak=<N>]`
>
> Reviewer poll. The author merges; I only review + LGTM.
> 1. List open PRs in `<repo>` matching `<filter>`.
> 2. **Compute this cycle's result**: "actionable" if there is ≥1 matching PR I
>    have not already LGTM'd or left feedback on **since its latest commit**;
>    otherwise "idle".
> 3. If **idle**: increment `idle_streak`. If `idle_streak >= <idle_stop>`, STOP
>    — do not re-arm, and end the turn silently (no user message). Otherwise
>    re-arm `send_later(delay_minutes=<cadence_min>)` with this same message and
>    the incremented `idle_streak`, silently.
> 4. If **actionable**: reset `idle_streak = 0`, run the **Review procedure** on
>    each such PR, then re-arm with `idle_streak = 0`.

## Review procedure (per PR needing review)

1. **Subscribe** (`subscribe_pr_activity`) so follow-up commits/comments push in
   real time. If a steward already watches it, note that and continue.
2. **Fetch** the diff (`pull_request_read` `get_diff`) and changed files.
3. **Review for correctness AND side effects** against what the PR claims to do:
   does it break existing behavior; does it introduce a regression; are error
   paths and edge cases handled. Check any repo-specific traps the user named
   (for the agent-sessions TD tracker: content-preserving promote that never
   clobbers hand-written prose outside `<!-- baseline:begin/end -->` markers,
   atomic file writes, machine-independent index keys, POSIX path normalization,
   UTC-consistent stems, the `baseline`↔`baseline_calibration` import cycle, and
   `REPO_ROOT` resolution after packaging/CLI changes).
4. **Validate locally** in `<worktree>`: `git fetch origin <head-ref>` &&
   checkout; run `python -m pytest -q` and, if configured, `python -m ruff check .`
   and `python -m mypy agent_sessions tools`. Confirm the change actually works —
   not just that tests pass. Return to the prior branch afterward.
5. **Comment** (`add_issue_comment`):
   - Correct → start with **`LGTM`** and a short bullet list of what you
     validated (tests/lint result, side effects checked) so the author can merge.
   - Problems → specific, actionable findings with `file:line` and why; withhold
     the LGTM.
6. **Never merge.** Only comment when there is an LGTM or actionable feedback;
   otherwise stay silent.

## Stop conditions

- `idle_streak` reaches `idle_stop` consecutive empty polls → the loop stops
  arming itself (the periodic sleep-wake alarm ends).
- The user says to stop → `delete_trigger` the pending wake-up and confirm.
- Re-invoking this skill after an auto-stop restarts the loop fresh with
  `idle_streak = 0`.

## Notes

- New-PR discovery latency ≈ `cadence_min`; PRs already subscribed get real-time
  push regardless of the poll.
- Because the idle counter lives in the alarm message, the loop is stateless
  across firings — no scratch file needed.
