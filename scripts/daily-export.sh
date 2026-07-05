#!/usr/bin/env bash
set -euo pipefail

pdf=0
push=1
python_cmd="${PYTHON:-python}"
sources=()

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
