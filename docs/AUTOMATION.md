# Automation

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-07-22`
> Covers the scheduled export job. For the pre-push CI parity harness
(`scripts/local_ci.sh` and the `pre-push` hook), see
[LOCAL_CI.md](LOCAL_CI.md).

This repo supports a local daily export job. The job is intentionally limited to
exporting sessions into local `archive/` artifacts, committing changed archive
metadata files, and pushing to the private GitHub repo. Search indexing and
baseline suggestion runs stay separate.

## Daily Export Contract

The scheduled job should:

1. `git pull --ff-only`
2. Optionally run `python tools/agent_archive.py status`
3. Run `python tools/agent_archive.py export --all`
4. Optionally include `--pdf`, or set `[archive] write_pdfs = true` in a
   machine-local `sources.toml`
5. Commit only when tracked metadata changed, usually `archive/index.jsonl` or
   `archive/INDEX.md`
6. Push only after a successful commit
7. Exit cleanly when there is nothing new

It should not:

- commit `raw/`
- commit machine-local `sources.toml`
- run cass indexing
- run `baseline suggest` daily until promotion is safer
- stage local-only Markdown/PDF transcript artifacts
- stage non-archive metadata files

## Windows

Manual run:

```powershell
.\scripts\daily-export.ps1
.\scripts\daily-export.ps1 -Pdf
.\scripts\daily-export.ps1 -Source codex-windows -Pdf
```

Task Scheduler sketch:

```powershell
$repo = "C:\Users\<user>\Projects\Agent Sessions"
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\daily-export.ps1`" -Pdf"
$trigger = New-ScheduledTaskTrigger -Daily -At 7:30am
Register-ScheduledTask -TaskName "Agent Sessions Daily Export" -Action $action -Trigger $trigger
```

## WSL/Linux

Manual run:

```bash
./scripts/daily-export.sh
./scripts/daily-export.sh --pdf
./scripts/daily-export.sh --source codex-windows --pdf
```

Cron sketch:

```cron
30 7 * * * cd "$HOME/Projects/Agent Sessions" && ./scripts/daily-export.sh --pdf >> "$HOME/agent-sessions-export.log" 2>&1
```

## Idempotency

The exporter preserves existing session import timestamps and `archive/INDEX.md`
generated timestamps when the underlying content is unchanged. That keeps daily
runs quiet when there are no new or changed source sessions.

Rendered transcript artifacts (`archive/**/*.md`, `archive/**/*.pdf`) are
local-only by default and ignored by Git. The portable repo state is
`archive/index.jsonl` plus `archive/INDEX.md`.

`archive/index.jsonl` is merge-aware: records already indexed from another
machine remain in the unified catalog even when the current machine cannot see
that other machine's local agent stores.

PDF generation skips existing PDFs unless the Markdown changed.
PDF generation is off by default. Enable it for a single run with `--pdf`, or
persist it for one machine with `[archive] write_pdfs = true` in ignored
`sources.toml`; use `--no-pdf` to force Markdown-only export for one run.
Only set `[archive] track_artifacts = true` if the repo should intentionally go
back to committing rendered transcript files.

## Hook Shape

Git hooks are not useful for detecting new sessions because the source files are
outside this repo. For near-real-time updates, use a filesystem watcher on the
configured source roots and debounce it before running:

```powershell
python .\tools\agent_archive.py status
.\scripts\daily-export.ps1 -Pdf
```

The debounce matters because agent tools can write JSONL/transcript files while
a session is still active.

## Schedule Choices

Recommended starting point: daily morning on each active machine, Markdown-only
by default. Enable PDFs only if the extra runtime and diff volume are acceptable.
A weekly baseline review can be added later after promotion and calibration
workflows mature.
