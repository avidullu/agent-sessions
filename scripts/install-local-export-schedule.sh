#!/usr/bin/env bash
# Install or remove a user crontab entry for scripts/local-export.sh.
# See docs/AUTOMATION.md.

set -euo pipefail

hour=7
minute=30
pdf=0
uninstall=0
log_dir="${AGENT_SESSIONS_LOG_DIR:-$HOME/.local/share/agent-sessions/logs}"
marker="# agent-sessions local-export (managed by install-local-export-schedule.sh)"

usage() {
  cat <<'EOF'
Usage: install-local-export-schedule.sh [options]

Install a user crontab job that runs scripts/local-export.sh daily.

Options:
  --hour N          Hour (0-23, default 7)
  --minute N        Minute (0-59, default 30)
  --pdf             Pass --pdf to local-export.sh
  --log-dir DIR     Log directory (default: ~/.local/share/agent-sessions/logs)
  --uninstall       Remove the managed crontab entry
  -h, --help        Show this help

The job is local-only (no git commit/push). Prefer this on a single primary
archive host, especially if remotes are a public product repository.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hour)
      hour="$2"
      shift 2
      ;;
    --minute)
      minute="$2"
      shift 2
      ;;
    --pdf)
      pdf=1
      shift
      ;;
    --log-dir)
      log_dir="$2"
      shift 2
      ;;
    --uninstall)
      uninstall=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$hour" =~ ^[0-9]+$ && "$hour" -ge 0 && "$hour" -le 23 ]]; then
  echo "invalid --hour: $hour" >&2
  exit 2
fi
if ! [[ "$minute" =~ ^[0-9]+$ && "$minute" -ge 0 && "$minute" -le 59 ]]; then
  echo "invalid --minute: $minute" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export_script="$repo_root/scripts/local-export.sh"
if [[ ! -x "$export_script" ]]; then
  chmod +x "$export_script" || true
fi
if [[ ! -f "$export_script" ]]; then
  echo "missing $export_script" >&2
  exit 1
fi

existing="$(crontab -l 2>/dev/null || true)"
# Drop previous managed block (marker line + following cron line if present).
filtered="$(
  printf '%s\n' "$existing" | awk -v marker="$marker" '
    $0 == marker { skip=1; next }
    skip == 1 { skip=0; next }
    { print }
  '
)"

if [[ "$uninstall" -eq 1 ]]; then
  if [[ -z "$(printf '%s' "$filtered" | sed '/^$/d')" ]]; then
    crontab -r 2>/dev/null || true
  else
    printf '%s\n' "$filtered" | crontab -
  fi
  echo "Removed managed local-export crontab entry (if present)."
  exit 0
fi

mkdir -p "$log_dir"
pdf_flag=""
if [[ "$pdf" -eq 1 ]]; then
  pdf_flag=" --pdf"
fi

# Use absolute path so cron does not depend on cwd.
cron_line="$minute $hour * * * $export_script --log-dir $(printf %q "$log_dir") --write-primary-marker$pdf_flag"

{
  printf '%s\n' "$filtered"
  # Ensure a trailing newline before our block when crontab was empty.
  if [[ -n "$filtered" && "$filtered" != *$'\n' ]]; then
    printf '\n'
  fi
  printf '%s\n' "$marker"
  printf '%s\n' "$cron_line"
} | sed '/^$/N;/^\n$/D' | crontab -

echo "Installed daily local-export at ${hour}:$(printf '%02d' "$minute")."
echo "  script: $export_script"
echo "  logs:   $log_dir"
echo "  mode:   local-only (no git commit/push)"
echo
echo "Verify with: crontab -l"
echo "Run once now: $export_script --log-dir $(printf %q "$log_dir") --write-primary-marker$pdf_flag"
