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
break_lock=0

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
  --break-lock          Remove an abandoned export lock before starting
  --write-primary-marker
                        Write archive/.primary-host (gitignored machine marker)
  -h, --help            Show this help

Environment:
  PYTHON                Default interpreter when --python is omitted
  AGENT_SESSIONS_LOG_DIR
                        Default for --log-dir when set
EOF
}

require_value() {
  local option="$1"
  local count="$2"
  local value="${3:-}"
  if [[ "$count" -lt 2 || "$value" == --* ]]; then
    echo "local-export: $option requires a value" >&2
    usage >&2
    exit 2
  fi
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
    --break-lock)
      break_lock=1
      shift
      ;;
    --python)
      require_value "$1" "$#" "${2:-}"
      python_cmd="$2"
      shift 2
      ;;
    --source)
      require_value "$1" "$#" "${2:-}"
      sources+=("$2")
      shift 2
      ;;
    --log-dir)
      require_value "$1" "$#" "${2:-}"
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

lock_dir="$repo_root/.local-export.lock"
lock_token="$$-$(date +%s)-${RANDOM:-0}"
if [[ "$break_lock" -eq 1 && -e "$lock_dir" ]]; then
  rm -rf -- "$lock_dir"
fi
if ! mkdir -- "$lock_dir" 2>/dev/null; then
  echo "local-export: lock exists at $lock_dir — another export may be running" >&2
  echo "local-export: after confirming no export is active, retry with --break-lock" >&2
  exit 1
fi
printf '%s\n' "$lock_token" >"$lock_dir/token"
{
  printf 'pid=%s\n' "$$"
  printf 'started=%s\n' "$(date -Iseconds 2>/dev/null || date)"
} >"$lock_dir/owner"
release_lock() {
  if [[ -f "$lock_dir/token" ]] && [[ "$(cat "$lock_dir/token")" == "$lock_token" ]]; then
    rm -rf -- "$lock_dir"
  fi
}
trap release_lock EXIT

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
