# scripts/

| Script | Purpose | Docs |
| --- | --- | --- |
| `local_ci.sh` | Run the CI gate set locally in a pinned, throwaway venv, with a drift guard against `.github/workflows/ci.yml`. | [docs/LOCAL_CI.md](../docs/LOCAL_CI.md) |
| `pre-push` | Opt-in git hook that runs `local_ci.sh` before a push and aborts it if a gate is red. | [docs/LOCAL_CI.md](../docs/LOCAL_CI.md) |
| `local-export.sh` / `local-export.ps1` | Local-only archive export (no git). Preferred on a single primary host or public product clones. | [docs/AUTOMATION.md](../docs/AUTOMATION.md) |
| `install-local-export-schedule.sh` / `.ps1` | Install/remove daily user cron (POSIX) or Scheduled Task (Windows) for local-export. | [docs/AUTOMATION.md](../docs/AUTOMATION.md) |
| `daily-export.sh` / `daily-export.ps1` | Export + commit catalog + optional push to a **private** archive remote. | [docs/AUTOMATION.md](../docs/AUTOMATION.md) |

## Before pushing

```bash
./scripts/local_ci.sh              # full CI verdict: ruff + mypy + pytest/coverage
./scripts/local_ci.sh --lint-only  # fast inner loop; NOT the CI verdict
```

Install the hook once per clone (hooks are not tracked by git):

```bash
ln -s ../../scripts/pre-push .git/hooks/pre-push
```

Bypasses, in increasing order of "I know what I am doing": a documentation-only
push is skipped automatically; `SKIP_LOCAL_CI=1 git push` skips the gates for one
push; `git push --no-verify` skips every hook. The classification fails closed —
anything it cannot resolve runs the gates.

The hook gates the **pushed commits**, not the checkout: if the working tree is
clean and is that commit it runs in place, otherwise it gates a throwaway
detached worktree at that sha and removes it afterwards. It never installs itself
and never writes to tracked files, the index, or git config; `local_ci.sh` does
write gitignored artifacts (`*.egg-info/`, `.coverage`). Both scripts need
bash ≥ 4.
