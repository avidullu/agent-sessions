#!/usr/bin/env bash
# Assert that every CI job this gate depends on actually RAN and SUCCEEDED.
#
# Why this exists
# ---------------
# Forgejo maps a SKIPPED job to `success` in the commit-status API. A job
# carrying `if:` therefore renders a green check on the pull request even
# though it never executed, and both a human reviewer and an automated merge
# gate read that green check as "this was tested". It was not.
#
# This was not hypothetical: `test-windows` carried
# `if: github.server_url == 'https://github.com'`, and because GitHub Actions
# is disabled on the backup mirror, that condition was never true on any
# forge. The native-Windows legs ran nowhere for weeks while reporting
# `CI / test (py 3.11, windows-latest) — success`.
#
# `needs.<job>.result` is the only value that distinguishes the two, so the
# gate asserts on it directly. The four Actions result values are `success`,
# `failure`, `cancelled` and `skipped`; only `success` passes here.
#
# Usage
# -----
#   ci-gate.sh [--allow-skipped JOB]... JOB=RESULT [JOB=RESULT ...]
#
# `--allow-skipped JOB` permits that one job to report `skipped` (for a
# genuinely optional leg). The skip is still reported loudly as NOT RUN so it
# can never be mistaken for coverage. Prefer not needing it.
#
# Deliberately dependency-free: no jq, no python, no network. A gate that can
# fail for an incidental reason is a gate people learn to re-run past.

set -Eeuo pipefail

allow_skipped=()
pairs=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-skipped)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "ci-gate: --allow-skipped requires a job name" >&2
        exit 2
      fi
      allow_skipped+=("$2")
      shift 2
      ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *=*)
      pairs+=("$1")
      shift
      ;;
    *)
      echo "ci-gate: expected JOB=RESULT, got: $1" >&2
      exit 2
      ;;
  esac
done

# Fail closed. An empty argument list means the workflow stopped passing job
# results in — that must never read as a pass.
if [[ ${#pairs[@]} -eq 0 ]]; then
  echo "ci-gate: no JOB=RESULT pairs were supplied." >&2
  echo "ci-gate: refusing to pass a gate that was given nothing to check." >&2
  exit 1
fi

is_allowed_skip() {
  local job="$1" allowed
  for allowed in ${allow_skipped[@]+"${allow_skipped[@]}"}; do
    [[ "$allowed" == "$job" ]] && return 0
  done
  return 1
}

failed=0
not_run=0
echo "ci-gate: job results"
for pair in "${pairs[@]}"; do
  job="${pair%%=*}"
  result="${pair#*=}"

  # An empty result means the job is not in `needs:` at all, so the expression
  # expanded to nothing. Treat it as a hard failure, not as an absent check.
  if [[ -z "$result" ]]; then
    printf '  %-32s %s\n' "$job" "<empty>"
    echo "::error::ci-gate: job '$job' reported an empty result; it is probably missing from needs:" >&2
    failed=1
    continue
  fi

  case "$result" in
    success)
      printf '  %-32s %s\n' "$job" "success"
      ;;
    skipped)
      if is_allowed_skip "$job"; then
        printf '  %-32s %s\n' "$job" "NOT RUN (skip explicitly allowed)"
        echo "::warning::ci-gate: job '$job' did NOT RUN on this forge - it provides no coverage for this commit"
        not_run=$((not_run + 1))
      else
        printf '  %-32s %s\n' "$job" "skipped"
        echo "::error::ci-gate: job '$job' was SKIPPED and therefore never ran. A skipped job is not a passing job." >&2
        failed=1
      fi
      ;;
    *)
      printf '  %-32s %s\n' "$job" "$result"
      echo "::error::ci-gate: job '$job' did not succeed (result=$result)" >&2
      failed=1
      ;;
  esac
done

if [[ "$failed" -ne 0 ]]; then
  echo
  echo "ci-gate: FAILED - do not merge." >&2
  exit 1
fi

echo
if [[ "$not_run" -ne 0 ]]; then
  # Never claim full coverage when part of it was skipped.
  echo "ci-gate: PASSED with $not_run job(s) NOT RUN - coverage is incomplete for this commit."
else
  echo "ci-gate: PASSED - every required job ran and succeeded."
fi
