#!/usr/bin/env bash
set -euo pipefail

pdf=0
push=1
python_cmd="${PYTHON:-python}"
sources=()
lock_timeout=300  # seconds before a stale lock is considered orphaned

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pdf)
      pdf=1
      shift
      ;;
    --no-push)
      push=0
      shift
      ;;
    --python)
      python_cmd="$2"
      shift 2
      ;;
    --source)
      sources+=("$2")
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# ── Guardrails ──────────────────────────────────────────────────────

# 1. Must be on main (or a user-configurable branch via DAILY_EXPORT_BRANCH).
required_branch="${DAILY_EXPORT_BRANCH:-main}"
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$required_branch" ]]; then
  echo "daily-export: must run on '$required_branch' branch (currently '$current_branch')" >&2
  echo "Set DAILY_EXPORT_BRANCH to override." >&2
  exit 1
fi

# 2. Working tree must be clean (no staged or unstaged changes).
if [[ -n "$(git status --porcelain)" ]]; then
  echo "daily-export: working tree is dirty — commit or stash changes first" >&2
  git status --short >&2
  exit 1
fi

# 3. Lock file to prevent concurrent export runs sharing the checkout.
lock_file="$repo_root/.daily-export.lock"
if [[ -f "$lock_file" ]]; then
  lock_age=$(($(date +%s) - $(stat -c %Y "$lock_file" 2>/dev/null || echo 0)))
  if [[ $lock_age -lt $lock_timeout ]]; then
    echo "daily-export: lock file exists (age=${lock_age}s) — another export may be running" >&2
    exit 1
  fi
  echo "daily-export: stale lock file (age=${lock_age}s > timeout=${lock_timeout}s), removing" >&2
  rm -f "$lock_file"
fi
trap 'rm -f "$lock_file"' EXIT
echo $$ > "$lock_file"

# ── Main export ─────────────────────────────────────────────────────

git pull --ff-only

export_args=(tools/agent_archive.py export)
if [[ ${#sources[@]} -gt 0 ]]; then
  for source in "${sources[@]}"; do
    export_args+=(--source "$source")
  done
else
  export_args+=(--all)
fi
if [[ "$pdf" -eq 1 ]]; then
  export_args+=(--pdf)
fi

"$python_cmd" "${export_args[@]}"

if [[ -z "$(git status --porcelain -- archive/)" ]]; then
  echo "No archive changes to commit."
  exit 0
fi

git add -- archive/
git commit -m "archive: daily export $(date +%F)"

if [[ "$push" -eq 1 ]]; then
  git push
fi
