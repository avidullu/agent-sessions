# Automation

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-08-05`
> Covers scheduled export jobs. For the pre-push CI parity harness
(`scripts/local_ci.sh` and the `pre-push` hook), see
[LOCAL_CI.md](LOCAL_CI.md).

This repo supports two automation modes:

| Mode | Scripts | Git? | When to use |
| --- | --- | --- | --- |
| **Local-only primary host** | `local-export.*` + `install-local-export-schedule.*` | No | Single machine is the archive source of truth; or remotes are a **public** product clone and personal catalogs must stay on disk |
| **Private catalog sync** | `daily-export.*` | Yes (`pull` / commit catalog / optional `push`) | You maintain a **private** archive remote and want multi-machine catalog convergence |

Search indexing and baseline suggestion runs stay separate from either job.

## What is tracked vs local-only?

| Path | Default Git behavior |
| --- | --- |
| `archive/**/*.md`, `archive/**/*.pdf` | **Ignored** — full transcripts stay local |
| `raw/` | **Ignored** — may contain secrets / full tool output |
| `sources.toml` | **Ignored** — machine-specific roots |
| `archive/index.jsonl`, `archive/INDEX.md` | **Not ignored** — portable catalog metadata |
| `archive/.primary-host` | **Ignored** — optional marker written by local-export |

If your remotes are the public GitHub/Forgejo **product** repositories, do **not**
commit personal `archive/index.jsonl` / `INDEX.md`. Prefer **local-only** mode.
Use **private catalog sync** only against a private archive remote you control.

## Local-only primary host (recommended default)

Export sessions into `archive/` on one machine, with optional daily schedule.
No branch checks, no clean-tree requirement, no git operations.

### One-shot

```bash
# Linux / WSL / macOS
./scripts/local-export.sh
./scripts/local-export.sh --pdf
./scripts/local-export.sh --source claude-linux --log-dir ~/.local/share/agent-sessions/logs
```

```powershell
# Windows
.\scripts\local-export.ps1
.\scripts\local-export.ps1 -Pdf
.\scripts\local-export.ps1 -LogDir "$env:LOCALAPPDATA\agent-sessions\logs" -WritePrimaryMarker
```

Useful flags:

- `--log-dir` / `-LogDir` — append a dated log file (also via `AGENT_SESSIONS_LOG_DIR`)
- `--write-primary-marker` / `-WritePrimaryMarker` — write gitignored `archive/.primary-host`
- `--no-status` / `-NoStatus` — skip the post-export status summary
- `--source` / `-Source` — limit to named source(s)
- `--break-lock` / `-BreakLock` — remove an abandoned lock after confirming no export is active

Local-only exports share the atomic `.local-export.lock` directory across Bash
and PowerShell, so overlapping cron, Scheduled Task, or manual runs fail instead
of writing the catalog concurrently. The lock is deliberately not expired by
age: a large valid export can run for more than a few minutes. If a host crash
leaves the lock behind, first confirm that no export process is active, then run
once with `--break-lock` (Bash) or `-BreakLock` (PowerShell). Lock cleanup is
ownership-checked so an older process cannot delete a newer process's lock.

### Install a daily schedule

```bash
# Linux / WSL / macOS (user crontab)
./scripts/install-local-export-schedule.sh
./scripts/install-local-export-schedule.sh --hour 7 --minute 30
./scripts/install-local-export-schedule.sh --pdf --log-dir ~/.local/share/agent-sessions/logs
./scripts/install-local-export-schedule.sh --uninstall
```

```powershell
# Windows (current-user Scheduled Task)
.\scripts\install-local-export-schedule.ps1
.\scripts\install-local-export-schedule.ps1 -Hour 7 -Minute 30 -Pdf
.\scripts\install-local-export-schedule.ps1 -Uninstall
```

The installer wires **local-export** only. It does not push to remotes.

### Single-host tips

1. Configure all agent roots this machine can see in ignored `sources.toml`
   (including Windows stores from WSL via `/mnt/c/Users/<you>/...` when useful).
2. Run exports only on the primary clone so you do not maintain two catalogs.
3. On secondary checkouts of the **product** repo, leave `sources.toml` empty or
   omit export schedules — use those trees for code/tooling, not a second archive.
4. Optional: `./scripts/local-export.sh --write-primary-marker` so humans can see
   which clone claimed the primary role.

## Private catalog sync (`daily-export`)

Use only when the remote is a **private** archive you intend to update with
catalog metadata.

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

### Windows

Manual run:

```powershell
.\scripts\daily-export.ps1
.\scripts\daily-export.ps1 -Pdf
.\scripts\daily-export.ps1 -Source codex-windows -Pdf
.\scripts\daily-export.ps1 -NoPush
```

Task Scheduler sketch (private remote only):

```powershell
$repo = "C:\Users\<user>\Projects\Agent Sessions"
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\daily-export.ps1`" -Pdf"
$trigger = New-ScheduledTaskTrigger -Daily -At 7:30am
Register-ScheduledTask -TaskName "Agent Sessions Daily Export" -Action $action -Trigger $trigger
```

Prefer `install-local-export-schedule.ps1` unless you explicitly need git push.

### WSL/Linux

Manual run:

```bash
./scripts/daily-export.sh
./scripts/daily-export.sh --pdf
./scripts/daily-export.sh --source codex-windows --pdf
./scripts/daily-export.sh --no-push
```

Cron sketch (private remote only):

```cron
30 7 * * * cd "$HOME/Projects/Agent Sessions" && ./scripts/daily-export.sh --pdf >> "$HOME/agent-sessions-export.log" 2>&1
```

`daily-export.sh` requires a clean working tree and the configured branch
(default `main`). If you keep an uncommitted personal catalog on a public clone,
use **local-export** instead.

## Idempotency

The exporter preserves existing session import timestamps and `archive/INDEX.md`
generated timestamps when the underlying content is unchanged. That keeps daily
runs quiet when there are no new or changed source sessions.

Rendered transcript artifacts (`archive/**/*.md`, `archive/**/*.pdf`) are
local-only by default and ignored by Git. The portable repo state for private
multi-machine sync is `archive/index.jsonl` plus `archive/INDEX.md`.

`archive/index.jsonl` is merge-aware: records already indexed from another
machine remain in the unified catalog even when the current machine cannot see
that other machine's local agent stores. Identical sessions seen from Windows
and WSL collapse on `session_id` + content hash when both are exported into one
catalog.

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

```bash
./scripts/local-export.sh
```

The debounce matters because agent tools can write JSONL/transcript files while
a session is still active.

## Schedule Choices

Recommended starting point: **local-only** daily morning on one primary host,
Markdown-only by default. Enable PDFs only if the extra runtime is acceptable.
Add private catalog push only when you have a private remote and want
cross-machine catalog merge. A weekly baseline review can be added later after
promotion and calibration workflows mature.
