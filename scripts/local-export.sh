#!/usr/bin/env bash
# Local-only session export for a primary archive host.
#
# Unlike daily-export.sh, this never runs git pull/commit/push. Use it when:
#   - this clone is your single source-of-truth archive on disk, or
#   - the remotes are a public product repo and personal catalogs must stay local.
#
# See docs/AUTOMATION.md.

set -euo pipefail

pdf=0
run_status=1
write_marker=0
python_cmd="${PYTHON:-python3}"
sources=()
log_dir=""
lock_timeout=300

usage() {
  cat <<'EOF'
Usage: local-export.sh [options]

Export configured agent sessions into archive/ without any git operations.

Options:
  --pdf                 Also write PDF transcripts (requires reportlab)
  --source NAME         Limit export to one source (repeatable)
  --python CMD          Python interpreter (default: python3, or $PYTHON)
  --log-dir DIR         Append a dated log under DIR (creates DIR if needed)
  --no-status           Skip `agent_archive status` after export
  --write-primary-marker
                        Write archive/.primary-host (gitignored machine marker)
  -h, --help            Show this help

Environment:
  PYTHON                Default interpreter when --python is omitted
  AGENT_SESSIONS_LOG_DIR
                        Default for --log-dir when set
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pdf)
      pdf=1
      shift
      ;;
    --no-status)
      run_status=0
      shift
      ;;
    --write-primary-marker)
      write_marker=1
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
    --log-dir)
      log_dir="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "local-export: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$log_dir" && -n "${AGENT_SESSIONS_LOG_DIR:-}" ]]; then
  log_dir="$AGENT_SESSIONS_LOG_DIR"
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v "$python_cmd" >/dev/null 2>&1; then
  if [[ "$python_cmd" == "python3" ]] && command -v python >/dev/null 2>&1; then
    python_cmd=python
  else
    echo "local-export: python interpreter not found: $python_cmd" >&2
    exit 1
  fi
fi

lock_file="$repo_root/.local-export.lock"
if [[ -f "$lock_file" ]]; then
  lock_age=$(($(date +%s) - $(stat -c %Y "$lock_file" 2>/dev/null || echo 0)))
  if [[ $lock_age -lt $lock_timeout ]]; then
    echo "local-export: lock file exists (age=${lock_age}s) — another export may be running" >&2
    exit 1
  fi
  echo "local-export: stale lock file (age=${lock_age}s > timeout=${lock_timeout}s), removing" >&2
  rm -f "$lock_file"
fi
trap 'rm -f "$lock_file"' EXIT
echo $$ >"$lock_file"

run_export() {
  local export_args=(tools/agent_archive.py export)
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

  echo "local-export: $(date -Iseconds 2>/dev/null || date) starting in $repo_root"
  "$python_cmd" "${export_args[@]}"

  if [[ "$run_status" -eq 1 ]]; then
    "$python_cmd" tools/agent_archive.py status
  fi

  if [[ "$write_marker" -eq 1 ]]; then
    mkdir -p "$repo_root/archive"
    {
      echo "primary-host=local"
      echo "repo=$repo_root"
      echo "updated=$(date -Iseconds 2>/dev/null || date)"
    } >"$repo_root/archive/.primary-host"
    echo "local-export: wrote archive/.primary-host"
  fi

  echo "local-export: done $(date -Iseconds 2>/dev/null || date)"
}

if [[ -n "$log_dir" ]]; then
  mkdir -p "$log_dir"
  log_file="$log_dir/export-$(date +%F).log"
  # shellcheck disable=SC2094
  run_export >>"$log_file" 2>&1
  echo "local-export: wrote $log_file"
else
  run_export
fi
