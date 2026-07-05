# Automation

This repo supports a local daily export job. The job is intentionally limited to
exporting sessions into `archive/`, committing changed archive files, and
pushing to the private GitHub repo. Search indexing and baseline suggestion runs
stay separate.

## Daily Export Contract

The scheduled job should:

1. `git pull --ff-only`
2. Run `python tools/agent_archive.py export --all`
3. Optionally include `--pdf`
4. Commit only when `archive/` changed
5. Push only after a successful commit
6. Exit cleanly when there is nothing new

It should not:

- commit `raw/`
- commit machine-local `sources.toml`
- run cass indexing
- run `baseline suggest` daily until promotion is safer
- stage non-archive files

## Windows

Manual run:

```powershell
.\scripts\daily-export.ps1
.\scripts\daily-export.ps1 -Pdf
.\scripts\daily-export.ps1 -Source codex-windows -Pdf
```

Task Scheduler sketch:

```powershell
$repo = "C:\Users\avidu\Projects\Agent Sessions"
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

PDF generation skips existing PDFs unless the Markdown changed.

## Schedule Choices

Recommended starting point: daily morning on each active machine, with `--pdf`
enabled only if the extra runtime is acceptable. A weekly baseline review can be
added later after promotion and calibration workflows mature.
