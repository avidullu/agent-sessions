# Multi-Machine Archive Model

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-08-05`
> Describes the per-machine local-store + shared-tracked-catalog model.

This repo can be a shared user-level archive. Each computer keeps its own local
agent stores, exports the sessions it can see, and (for private remotes) may push
catalog metadata back. Rendered Markdown/PDF transcript artifacts are local-only
by default.

### Single primary host (simplest)

If one machine can see every store you care about (for example WSL with both
`$HOME` and `/mnt/c/Users/...` Windows roots), keep **one** clone as the archive
source of truth and schedule **local-only** export:

```bash
./scripts/install-local-export-schedule.sh
```

Do not run `daily-export` against public product remotes. See
[AUTOMATION.md](AUTOMATION.md).

### Planned: SSH fleet collect (primary pulls remotes)

When other machines are only reachable over SSH, a **primary host** can pull
session stores on a lightweight hourly schedule, index them locally, and
optionally ship one exact catalog snapshot back with a separate manual command
and scoped, single-use approval.
Design and PR-sized tracker (not implemented yet):

→ [SSH_FLEET_COLLECT_PLAN.md](SSH_FLEET_COLLECT_PLAN.md) (**DRAFT**).

## How Machines Converge

For a practical bootstrap checklist, see
[NEW_MACHINE_SETUP.md](NEW_MACHINE_SETUP.md).

1. Clone this private repo on each computer.
2. Configure local source roots with `sources.toml` only when defaults are not
   enough. Keep `sources.toml` uncommitted.
3. Run `python tools/agent_archive.py status` to see what that computer can see
   and what is already indexed.
4. Run `python tools/agent_archive.py export --all` from that computer.
5. Commit and push only metadata changes, usually `archive/index.jsonl` and
   `archive/INDEX.md`.

Enable PDFs for one run with `--pdf`, or persist them per machine with
`[archive] write_pdfs = true` in ignored `sources.toml`. Use `--no-pdf` to force
Markdown-only export for one run even when the local config enables PDFs.
Set `[archive] track_artifacts = true` only when you intentionally want rendered
Markdown/PDF transcript files back in Git.

The exporter now merges new local records into the existing `archive/index.jsonl`
instead of replacing the index with only the current computer's visible files.
Records are merged on a machine-independent identity — the session's
`metadata.session_id` when present, falling back to `(source name, source file
path)` for older exports that predate a session id. Because the identity is the
session rather than an absolute path, the same logical session exported from two
machines (whose absolute source-file paths differ) collapses to a single record,
and re-exporting a changed file still replaces the older entry for that session.
Records from other computers stay in the index even when their local stores are
not visible from the current machine.

Existing rows written under the old path-only keying are left as-is; a one-time
backfill and a `regenerate` (backup-and-rebuild) path are tracked separately, and
`agent-archive prune` drops index rows whose archive Markdown no longer exists.
Do not hand-edit the archive index during setup to solve old duplicate/stale
records; use the future backfill/regenerate path tracked in issue #32.

## Unified User View

The unified view is built from committed archive metadata:

- `archive/index.jsonl` is the merged catalog used by baseline and reporting
  commands.
- `archive/INDEX.md` is the human-readable catalog.
- `archive/**/*.md` and optional PDFs are local rendered artifacts; regenerate
  them on any machine that has access to the matching source logs.
- `python tools/agent_archive.py status` reports visible files, new files,
  changed files, records not visible from the current machine, and best-effort
  origin environments.

This lets baseline extraction reason over the user's combined history across
machines and agents, not only the sessions visible on the machine running the
latest export.

## Origin Environments

Current archives do not include an explicit physical-machine id, so origin
reporting is inferred from source file paths. For example:

- `C:/Users/<user>` paths are grouped as Windows user environments.
- `\\wsl.localhost\<distro>\home\<user>` paths are grouped as WSL user
  environments.
- `/home/<user>` paths are grouped as POSIX home environments.

This is good enough to distinguish local environments, but it is not proof of
distinct physical computers. A future enhancement should add an explicit
machine id, preferably from `AGENT_ARCHIVE_MACHINE_ID` with a hostname fallback,
to make multi-computer reporting exact.

## Hooks And Watchers

Git hooks do not detect new sessions because agent session files live outside
this repo. Prefer one of these:

- Scheduled polling: Task Scheduler, cron, or systemd timers run
  `scripts/daily-export.*`.
- File watchers: PowerShell `FileSystemWatcher` or Linux `inotifywait` watches
  configured source roots, then runs `status` and a debounced export.

Scheduled polling is the safest first step because agents often write session
files while a conversation is still active. Watchers should wait for the file
mtime and size to settle before exporting.
