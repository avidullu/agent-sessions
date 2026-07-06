# Multi-Machine Archive Model

This repo is the shared user-level archive. Each computer keeps its own local
agent stores, exports the sessions it can see, and pushes Markdown/PDF archive
artifacts back to the private GitHub repo.

## How Machines Converge

1. Clone this private repo on each computer.
2. Configure local source roots with `sources.toml` only when defaults are not
   enough. Keep `sources.toml` uncommitted.
3. Run `python tools/agent_archive.py status` to see what that computer can see
   and what is already indexed.
4. Run `python tools/agent_archive.py export --all --pdf` from that computer.
5. Commit and push only `archive/` changes.

The exporter now merges new local records into the existing `archive/index.jsonl`
instead of replacing the index with only the current computer's visible files.
Records are keyed by source name and source file path. When a source file is
exported again with a changed digest, the current record replaces the older
index entry for that same source file. Records from other computers stay in the
index even when their local stores are not visible from the current machine.

## Unified User View

The unified view is built from committed archive artifacts:

- `archive/**/*.md` and optional PDFs are the durable session exports.
- `archive/index.jsonl` is the merged catalog used by baseline and reporting
  commands.
- `archive/INDEX.md` is the human-readable catalog.
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
