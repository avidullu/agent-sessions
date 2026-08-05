# New-Machine Setup Checklist

> **Status:** `Active (reference)` · **Owner:** `avidullu` · **Last updated:** `2026-07-22`
> Copy/paste checklist for adding a computer to the shared archive.

Use this when adding another Windows, WSL, or Linux environment to the shared
private archive. The goal is to confirm that local agent stores are discovered,
exports converge with the existing archive, and only intended archive artifacts
are committed.

## Before You Start

- Use Python 3.11 or newer.
- Authenticate GitHub for this private repo.
- Keep machine-local source overrides in ignored `sources.toml`.
- Do not commit raw logs from `raw/` unless there is an explicit reason.
- Pull with `git pull --ff-only` before reading or changing the repo.

## 1. Clone Or Refresh

Windows PowerShell:

```powershell
git clone https://github.com/avidullu/agent-sessions "C:\Users\<you>\Projects\Agent Sessions"
cd "C:\Users\<you>\Projects\Agent Sessions"
git pull --ff-only
```

WSL/Linux:

```bash
git clone https://github.com/avidullu/agent-sessions "$HOME/Projects/Agent Sessions"
cd "$HOME/Projects/Agent Sessions"
git pull --ff-only
```

If the repo already exists, skip `git clone` and run `git pull --ff-only` from
the existing checkout.

## 2. Install Tooling

```powershell
python -m pip install -e ".[dev]"
```

The `dev` extra installs test tools and PDF support (`reportlab`). A minimal
install can still export Markdown, but PDF output requires `reportlab`.

Verify PDF support:

```powershell
python -c "import reportlab; print('reportlab ok')"
```

## 3. Validate The Repo

Run the same gates CI expects:

```powershell
python -m pytest --cov=agent_sessions --cov-report=term-missing
python -m ruff check .
python -m mypy agent_sessions tools
```

Optional baseline sanity check:

```powershell
python tools/agent_archive.py baseline eval --dry-run
```

## 4. Discover Local Sources

```powershell
python tools/agent_archive.py discover --write docs/DISCOVERY.md
python tools/agent_archive.py status
```

Expected behavior:

- `docs/DISCOVERY.md` is refreshed with configured source roots, whether each
  root exists, matching file counts, and samples.
- `status` prints indexed records, visible configured files, new files, changed
  files, records not visible from this machine, source counts, and origin
  environments.
- Copilot/ZAI inventory sources can appear as skipped inventory-only sources.
  That is expected unless transcript files are available in known locations.

If defaults miss local paths, copy `sources.example.toml` to `sources.toml` and
edit roots for this machine. Keep `sources.toml` uncommitted.

If this machine will be the **only** archive host (for example WSL that can also
see Windows stores under `/mnt/c/Users/...`), install local-only daily export
after the first successful export — see [AUTOMATION.md](AUTOMATION.md)
(`install-local-export-schedule`). Do not point `daily-export` at public product
remotes.

## 5. Dry-Run Export

```powershell
python tools/agent_archive.py export --all --dry-run
```

This confirms extractor coverage without writing archive files. It should report
how many session files would export and which inventory-only sources were
skipped.

## 6. First Export

Markdown only:

```powershell
python tools/agent_archive.py export --all
```

Markdown plus PDFs:

```powershell
python tools/agent_archive.py export --all --pdf
```

PDF generation is off by default. To make PDFs the default on one machine, add
`write_pdfs = true` under `[archive]` in ignored `sources.toml`; use
`--no-pdf` to force Markdown-only export for one run.

Rendered Markdown/PDF transcript files are local-only by default. Git tracks the
catalog metadata (`archive/index.jsonl`, `archive/INDEX.md`) but ignores
`archive/**/*.md` and `archive/**/*.pdf`. Set `[archive] track_artifacts = true`
only for an intentional repo policy change back to committed transcript bodies.

Expected changed paths:

- `archive/index.jsonl`
- `archive/INDEX.md`
- local-only `archive/**/*.md`
- local-only `archive/**/*.pdf`, only when PDF export is enabled and `reportlab` is installed

If `--copy-raw` is used, raw gzip backups land in `raw/`, which is ignored by
Git by default.

## 7. Confirm Convergence

```powershell
python tools/agent_archive.py status
git status --short archive/index.jsonl archive/INDEX.md docs/DISCOVERY.md
```

For a first run on a new machine, it is normal to see:

- new visible files exported from this machine;
- records not visible from this machine, preserved from other machines;
- source counts that include agents this machine cannot currently see;
- origin environments for Windows, WSL, or POSIX homes.

The important invariant: committed records from other machines stay in
`archive/index.jsonl` instead of being replaced by only the current machine's
visible files.

## 8. Commit Or Open A PR

Stage explicit paths only:

```powershell
git add docs/DISCOVERY.md archive
git status --short
```

Commit and push directly only when the owner has explicitly approved a one-time
archive sync. Otherwise branch from the remote base and open a PR.

Do not stage:

- `sources.toml`
- `raw/`
- unrelated docs/code changes
- local editor or environment files

## 9. Optional Scheduled Sync

After manual validation succeeds, choose a sync mode:

- manual export only when requested;
- scheduled daily export with Task Scheduler, cron, or systemd timers;
- filesystem watcher with debounce.

See `docs/AUTOMATION.md` for the exact scripts and scheduler examples.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `git pull --ff-only` refuses to update | Stop before changing files. The branch may have local work or diverged history; inspect `git status --short --branch`. |
| `status` shows many records not visible from this machine | Usually expected on a multi-machine archive; those records are preserved from other environments. |
| `discover` reports missing roots | Add machine-local overrides in ignored `sources.toml`, or ignore sources that do not exist on this computer. |
| `export --all --pdf` says PDF support is missing | Install `reportlab`, or use Markdown-only export. |
| Copilot/ZAI sources are skipped | They are inventory-only until transcript files are present in supported locations. |
| `git status` is very large after export | Narrow the view with `git status --short archive/index.jsonl archive/INDEX.md docs/DISCOVERY.md`; stage explicit paths only. |
| Duplicate old archive records or stale filenames remain | One-time backfill and `regenerate` are tracked separately in issue #32. Do not hand-edit the archive index to solve this. |
