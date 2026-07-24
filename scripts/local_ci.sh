#!/usr/bin/env bash
set -euo pipefail

# Run the CI gate set locally, in a clean environment, before pushing.
#
# Why: CI is the only place the gates ran, so "works on my machine" and "green
# on CI" were independent facts. H1 (#82) was a test that failed on the local
# 3.12.3 interpreter while CI stayed green; H2b (#85) was the same gate set
# resolving to different tool versions on different days. This script closes
# both gaps by running CI's exact commands against CI's exact toolchain.
#
# See docs/LOCAL_CI.md.

# `mapfile` in the drift guard is a bash 4 builtin. macOS ships bash 3.2 as
# /bin/bash, which `#!/usr/bin/env bash` finds first unless a newer one is on
# PATH — without this guard the failure surfaces as "mapfile: command not found"
# from inside the drift guard, which reads like a broken guard.
if [[ -z "${BASH_VERSINFO:-}" ]] || (( BASH_VERSINFO[0] < 4 )); then
  echo "local_ci: needs bash >= 4 (found ${BASH_VERSION:-unknown})." >&2
  echo "local_ci: on macOS, 'brew install bash' and run it with that bash." >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage: scripts/local_ci.sh [options]

Runs the same gates as .github/workflows/ci.yml, in a throwaway venv built from
constraints-dev.txt.

Options:
  --lint-only     Run ruff + mypy only. Faster, but NOT verdict parity with CI.
  --venv DIR      Reuse (and create if missing) a persistent venv at DIR instead
                  of a throwaway one. Speeds up repeat runs; DIR must be
                  gitignored.
  --python BIN    Base interpreter used to build the venv (default: $PYTHON,
                  else python3, else python).
  -h, --help      Show this help.

Environment:
  PYTHON          Same as --python.
  LOCAL_CI_VENV   Same as --venv.
EOF
}

lint_only=0
python_cmd="${PYTHON:-}"
venv_dir="${LOCAL_CI_VENV:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lint-only)
      lint_only=1
      shift
      ;;
    --venv)
      if [[ $# -lt 2 ]]; then
        echo "local_ci: --venv requires a directory" >&2
        usage >&2
        exit 2
      fi
      venv_dir="$2"
      shift 2
      ;;
    --python)
      if [[ $# -lt 2 ]]; then
        echo "local_ci: --python requires an interpreter" >&2
        usage >&2
        exit 2
      fi
      python_cmd="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "local_ci: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# Captured before the cd so a relative --venv resolves against where the user
# invoked the script, not against the repo root.
invocation_cwd="$PWD"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

workflow=".github/workflows/ci.yml"
constraints="constraints-dev.txt"

# ── Gate definitions ────────────────────────────────────────────────
#
# Single source of truth. Each array is one `run:` line from the workflow,
# tokenised. The drift guard compares these arrays against the workflow, and the
# gates below execute these same arrays with element 0 (`python`) swapped for the
# venv interpreter. There is deliberately no second copy of a command string to
# forget to update.
#
# Tool versions are NOT listed here: constraints-dev.txt (H2b) is the only pin
# source, and it is consumed, never transcribed, so pins cannot drift between
# this script and CI.

ci_install=(python -m pip install -e ".[dev]" -c constraints-dev.txt)
ci_ruff=(python -m ruff check .)
ci_mypy=(python -m mypy agent_sessions tools tests)
ci_pytest=(python -m pytest --cov=agent_sessions --cov-report=term-missing --cov-fail-under=92)
ci_linkcheck=(python -m tools.check_md_links)
ci_pii=(python -m tools.check_pii)

# The install line appears once per job; the workflow has four jobs now
# (test, lint, link-check, pii-check). The link-check and pii-check jobs have
# no install step — they only need Python stdlib.
expected_runs=(
  "${ci_install[*]}"
  "${ci_install[*]}"
  "${ci_ruff[*]}"
  "${ci_mypy[*]}"
  "${ci_pytest[*]}"
  "${ci_linkcheck[*]}"
  "${ci_pii[*]}"
)

expected_python_versions=(3.11 3.12 3.13)

# Every runner CI uses, and the extra `include:` legs beyond the primary matrix,
# as "<os> <python-version>". The closing summary is derived from these rather
# than hardcoded, so deleting the Windows leg can no longer leave this script
# claiming coverage CI stopped providing.
expected_os=(ubuntu-latest windows-latest)
expected_matrix_include=("windows-latest 3.11" "windows-latest 3.12" "windows-latest 3.13")

# ── Drift guard ─────────────────────────────────────────────────────
#
# Runs before any work so a diverged script costs a second, not a venv build.
# A guard that passes when it cannot find what it is looking for is worse than
# no guard, so every check here fails on absence as well as on mismatch.

drift_fail() {
  echo "local_ci: DRIFT DETECTED — $1" >&2
  shift
  local line
  for line in "$@"; do
    printf '%s\n' "$line" | sed 's/^/  /' >&2
  done
  echo >&2
  echo "This script no longer mirrors $workflow. Update the gate arrays at the" >&2
  echo "top of scripts/local_ci.sh (and docs/LOCAL_CI.md) to match, or revert" >&2
  echo "the workflow change. Do not bypass: a stale guard is how local and CI" >&2
  echo "silently disagree again." >&2
  exit 1
}

# Quotes are a YAML/bash formatting detail, not a semantic difference: CI writes
# `-e ".[dev]"` while the bash array holds `.[dev]`. Compare the tokens.
normalize_cmd() {
  tr -d "\"'" | tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//'
}

[[ -f "$workflow" ]] || drift_fail "$workflow is missing." \
  "The gate set this script mirrors no longer exists."

# D7: exactly one workflow file, executed by both GitHub and Forgejo. A second
# one would be a gate set this script does not mirror and does not report on.
workflow_count="$(find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) | wc -l)"
if [[ "$workflow_count" -ne 1 ]]; then
  drift_fail "found $workflow_count workflow files under .github/workflows/, expected exactly 1 (D7)." \
    "This script only mirrors $workflow."
fi
if [[ -d .forgejo/workflows ]]; then
  drift_fail ".forgejo/workflows/ exists." \
    "D7: Forgejo executes .github/workflows/ directly; a second workflow file must not exist."
fi

mapfile -t workflow_runs < <(sed -n 's/^[[:space:]]*run:[[:space:]]*//p' "$workflow")
if [[ ${#workflow_runs[@]} -eq 0 ]]; then
  drift_fail "no 'run:' steps found in $workflow." \
    "Either the workflow changed shape (multi-line 'run: |' blocks?) or it stopped running commands."
fi

normalized_runs=()
for run_line in "${workflow_runs[@]}"; do
  normalized_runs+=("$(printf '%s' "$run_line" | normalize_cmd)")
done

normalized_expected=()
for run_line in "${expected_runs[@]}"; do
  normalized_expected+=("$(printf '%s' "$run_line" | normalize_cmd)")
done

actual_sorted="$(printf '%s\n' "${normalized_runs[@]}" | sort)"
expected_sorted="$(printf '%s\n' "${normalized_expected[@]}" | sort)"
if [[ "$actual_sorted" != "$expected_sorted" ]]; then
  # Comparing the whole multiset — not just version pins — is what catches an
  # added job, a dropped `-c constraints-dev.txt`, or a changed gate flag.
  only_ci="$(comm -13 <(printf '%s\n' "$expected_sorted") <(printf '%s\n' "$actual_sorted") || true)"
  only_local="$(comm -23 <(printf '%s\n' "$expected_sorted") <(printf '%s\n' "$actual_sorted") || true)"
  details=()
  if [[ -n "$only_ci" ]]; then
    details+=("In CI but not run locally:" "$(printf '%s' "$only_ci" | sed 's/^/  /')")
  fi
  if [[ -n "$only_local" ]]; then
    details+=("Run locally but no longer in CI:" "$(printf '%s' "$only_local" | sed 's/^/  /')")
  fi
  drift_fail "the gate commands in $workflow do not match this script." ${details[@]+"${details[@]}"}
fi

# Matrix legs are a parity limit worth knowing about: this script can only run
# one interpreter, so the version list changing means the local verdict now
# covers a different slice of CI than it used to.
mapfile -t ci_python_versions < <(
  sed -n 's/^[[:space:]]*python-version:[[:space:]]*//p' "$workflow" |
    # shellcheck disable=SC2016  # matching a literal Actions ${{ }} expression
    grep -v '\${{' |
    tr -d '"[]' |
    tr ',' '\n' |
    sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' |
    grep -v '^$' |
    sort -u
)
if [[ ${#ci_python_versions[@]} -eq 0 ]]; then
  drift_fail "no literal python-version values found in $workflow."
fi
if [[ "$(printf '%s\n' "${ci_python_versions[@]}")" != "$(printf '%s\n' "${expected_python_versions[@]}" | sort -u)" ]]; then
  drift_fail "the CI Python matrix changed." \
    "CI now tests: $(printf '%s ' "${ci_python_versions[@]}")" \
    "This script expects: $(printf '%s ' "${expected_python_versions[@]}")"
fi

# A `run:` line only means "enforced gate" while nothing neuters it. `if: false`
# and `continue-on-error: true` leave the run lines byte-identical while turning
# the gate off, and a workflow- or job-level `env:` block can change what a run
# line does (PYTEST_ADDOPTS). None of these exist today, so their appearance is
# by definition a change this script does not mirror.
neutering="$(grep -nE '^[[:space:]]*(-[[:space:]]*)?(if|continue-on-error|env):' "$workflow" || true)"
if [[ -n "$neutering" ]]; then
  drift_fail "$workflow now uses if:/continue-on-error:/env:, which can disable or alter a gate without changing its 'run:' line." \
    "$(printf '%s' "$neutering" | sed 's/^/  /')" \
    "This guard compares run: lines; it cannot see a gate that CI no longer enforces."
fi

# Runner coverage. The Python matrix is guarded above; the OS matrix is the other
# half, and it is the half the closing summary makes a claim about.
mapfile -t ci_os < <(
  sed -n 's/^[[:space:]]*-\{0,1\}[[:space:]]*os:[[:space:]]*//p' "$workflow" |
    # shellcheck disable=SC2016  # matching a literal Actions ${{ }} expression
    grep -v '\${{' |
    tr -d '"[]' |
    tr ',' '\n' |
    sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' |
    grep -v '^$' |
    sort -u
)
if [[ ${#ci_os[@]} -eq 0 ]]; then
  drift_fail "no literal 'os:' matrix values found in $workflow."
fi
if [[ "$(printf '%s\n' "${ci_os[@]}")" != "$(printf '%s\n' "${expected_os[@]}" | sort -u)" ]]; then
  drift_fail "the CI runner matrix changed." \
    "CI now runs on: $(printf '%s ' "${ci_os[@]}")" \
    "This script expects: $(printf '%s ' "${expected_os[@]}")"
fi

# The `include:` legs, as "<os> <python-version>" pairs.
mapfile -t ci_include < <(
  awk '
    /^[[:space:]]*include:[[:space:]]*$/ { inc = 1; next }
    inc && /^[[:space:]]*steps:/ { inc = 0 }
    inc && /os:[[:space:]]*/ {
      line = $0; sub(/.*os:[[:space:]]*/, "", line); gsub(/["\x27]/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line); os = line; next
    }
    inc && /python-version:[[:space:]]*/ {
      line = $0; sub(/.*python-version:[[:space:]]*/, "", line); gsub(/["\x27]/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      if (os != "") { print os " " line; os = "" }
      next
    }
  ' "$workflow" | sort -u
)
if [[ "$(printf '%s\n' ${ci_include[@]+"${ci_include[@]}"})" != "$(printf '%s\n' "${expected_matrix_include[@]}" | sort -u)" ]]; then
  drift_fail "the CI matrix 'include:' legs changed." \
    "CI now includes: $(printf '%s; ' ${ci_include[@]+"${ci_include[@]}"})" \
    "This script expects: $(printf '%s; ' "${expected_matrix_include[@]}")"
fi

# The pins themselves live in constraints-dev.txt and are used, not copied. What
# this script has to defend is that they stay *exact* — a single `>=` sneaking
# back in restores the H2b drift the file was created to stop.
[[ -f "$constraints" ]] || drift_fail "$constraints is missing." \
  "CI installs with -c $constraints; without it the local toolchain is unpinned."
# Comments are stripped first and the whole requirement is matched: an
# unanchored `grep '=='` waved through `requests>=2.0  # not really ==pinned`,
# which is exactly the H2b drift this file exists to stop.
loose_pins="$(
  sed -e 's/[[:space:]]#.*$//' -e 's/^#.*$//' "$constraints" |
    grep -vE '^[[:space:]]*$' |
    grep -vE '^[[:space:]]*[A-Za-z0-9][A-Za-z0-9._-]*(\[[^]]*\])?==[^[:space:]#]+[[:space:]]*$' || true
)"
if [[ -n "$loose_pins" ]]; then
  drift_fail "$constraints contains non-exact pins." \
    "$(printf '%s' "$loose_pins" | sed 's/^/  /')" \
    "Every line must pin with '=='; see the file header."
fi

echo "Drift guard: OK (gate commands, Python/OS matrix, and pins match $workflow)"

# ── Environment ─────────────────────────────────────────────────────

if [[ -z "$python_cmd" ]]; then
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      python_cmd="$candidate"
      break
    fi
  done
fi
if [[ -z "$python_cmd" ]] || ! command -v "$python_cmd" >/dev/null 2>&1; then
  echo "local_ci: no Python interpreter found (tried \$PYTHON, python3, python)" >&2
  exit 1
fi

# `command -v` only proves something is executable, not that it is a working
# interpreter: `--python /bin/false` used to die here with no message at all,
# because set -e fired on this assignment.
probe_version() {
  "$1" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null
}
if ! base_version="$(probe_version "$python_cmd")" || [[ -z "$base_version" ]]; then
  echo "local_ci: '$python_cmd' is not a working Python interpreter" >&2
  exit 1
fi

echo "Repo:   $repo_root"
echo "Base:   Python $base_version ($python_cmd)"

if [[ -n "$venv_dir" ]]; then
  case "$venv_dir" in
    /*) ;;
    *) venv_dir="$invocation_cwd/$venv_dir" ;;
  esac
  venv_parent="$(dirname "$venv_dir")"
  # Resolved in two steps on purpose: `x="$(cd A && pwd)/$(basename B)"` takes
  # its exit status from the LAST substitution, so a failed cd used to slip past
  # set -u/-e and silently retarget the venv to /<basename>.
  if ! venv_parent="$(cd "$venv_parent" 2>/dev/null && pwd)"; then
    echo "local_ci: --venv parent directory does not exist: $(dirname "$venv_dir")" >&2
    exit 2
  fi
  venv_dir="$venv_parent/$(basename "$venv_dir")"
  # Only meaningful for a venv inside the checkout; outside it, git status can
  # never see it.
  if [[ "$venv_dir" == "$repo_root/"* ]] &&
    command -v git >/dev/null 2>&1 &&
    ! git check-ignore -q "$venv_dir" 2>/dev/null; then
    echo "local_ci: WARNING — $venv_dir is inside the repo and not gitignored;" >&2
    echo "local_ci: add it to .gitignore so it cannot be committed by accident." >&2
  fi
  echo "Venv:   $venv_dir (reused — additive, not a clean-checkout verdict)"
else
  venv_dir="$(mktemp -d -t agent-sessions-local-ci-XXXXXX)"
  # Throwaway by default so the verdict reflects a clean checkout, not whatever
  # the developer happens to have installed. Removed even on failure.
  trap 'rm -rf "$venv_dir"' EXIT
  echo "Venv:   $venv_dir (throwaway)"
fi

# Windows venvs use Scripts/python.exe, POSIX ones bin/python. Probing both is
# what stops a Git Bash run from rebuilding the venv every time and then blaming
# PyPI for an exit-127 "install failure".
find_venv_python() {
  local dir="$1" candidate
  for candidate in "$dir/bin/python" "$dir/Scripts/python.exe"; do
    if [[ -x "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! venv_python="$(find_venv_python "$venv_dir")"; then
  "$python_cmd" -m venv "$venv_dir"
  if ! venv_python="$(find_venv_python "$venv_dir")"; then
    echo "local_ci: no interpreter found in $venv_dir after 'python -m venv'." >&2
    echo "local_ci: expected $venv_dir/bin/python or $venv_dir/Scripts/python.exe." >&2
    exit 1
  fi
fi

# The gates run on THIS interpreter, so every version claim below is derived from
# it, not from the base interpreter. A reused --venv is not necessarily built
# from --python: it may predate a system upgrade entirely.
if ! venv_version="$(probe_version "$venv_python")" || [[ -z "$venv_version" ]]; then
  echo "local_ci: '$venv_python' is not a working Python interpreter" >&2
  exit 1
fi
venv_minor="${venv_version%.*}"
base_minor="${base_version%.*}"
if [[ "$venv_minor" != "$base_minor" ]]; then
  echo "local_ci: FAILED — the venv at $venv_dir runs Python $venv_version," >&2
  echo "local_ci: but the requested base interpreter is $base_version ($python_cmd)." >&2
  echo "local_ci: reporting one and testing the other is how a false verdict happens." >&2
  echo "local_ci: delete the venv (or pass a matching --python) and re-run." >&2
  exit 1
fi

echo "Python: $venv_version (gates run here)"

matched=0
for version in "${expected_python_versions[@]}"; do
  if [[ "$venv_minor" == "$version" ]]; then
    matched=1
  fi
done
if [[ "$matched" -eq 0 ]]; then
  # Not fatal: one interpreter can never cover a 4-leg matrix anyway. But the
  # developer should know their green is a weaker claim than CI's.
  echo "local_ci: WARNING — running on Python $venv_version, which CI does not test" >&2
  echo "local_ci: CI tests ${expected_python_versions[*]}; a pass here does not prove those legs" >&2
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1

echo
echo "── Install ──────────────────────────────────────────────────────"
echo "\$ ${ci_install[*]}"
# Tools are always invoked as `<venv>/bin/python -m <tool>`, never as a bare
# `ruff`/`pytest` from PATH: on a machine with conda or a ~/.local install, PATH
# resolves to a different interpreter than the one just provisioned.
install_status=0
"$venv_python" "${ci_install[@]:1}" || install_status=$?
if [[ "$install_status" -ne 0 ]]; then
  echo >&2
  echo "local_ci: FAILED — could not install the pinned toolchain (exit $install_status)." >&2
  if [[ "$install_status" -eq 127 ]]; then
    echo "local_ci: $venv_python could not be executed — the venv looks broken." >&2
  else
    echo "local_ci: this step needs network access to PyPI." >&2
  fi
  exit 1
fi

# ── Gates ───────────────────────────────────────────────────────────
#
# Cheapest first, but a failure does not stop the run: the whole set is ~10s, and
# a developer fixing lint should learn in the same pass that mypy is also red.

gate_names=()
gate_status=()
failures=0

run_gate() {
  local name="$1"
  shift
  echo
  echo "── $name ────────────────────────────────────────────────────────"
  echo "\$ $*"
  local start
  start="$(date +%s)"
  local status=0
  "$venv_python" "${@:2}" || status=$?
  local elapsed=$(( $(date +%s) - start ))
  gate_names+=("$name")
  if [[ "$status" -eq 0 ]]; then
    gate_status+=("PASS (${elapsed}s)")
    echo "$name: OK"
  else
    gate_status+=("FAIL (exit $status, ${elapsed}s)")
    failures=$((failures + 1))
    echo "$name: FAILED (exit $status)" >&2
  fi
}

run_gate "ruff" "${ci_ruff[@]}"
run_gate "mypy" "${ci_mypy[@]}"
run_gate "md-links" "${ci_linkcheck[@]}"
run_gate "pii" "${ci_pii[@]}"
if [[ "$lint_only" -eq 0 ]]; then
  run_gate "pytest" "${ci_pytest[@]}"
fi

# ── Summary ─────────────────────────────────────────────────────────

echo
echo "── Summary ──────────────────────────────────────────────────────"
for i in "${!gate_names[@]}"; do
  printf '  %-8s %s\n' "${gate_names[$i]}" "${gate_status[$i]}"
done

if [[ "$lint_only" -eq 1 ]]; then
  echo
  echo "  --lint-only: the test gate was SKIPPED. This is not the CI verdict."
  echo "  Run it before pushing:"
  echo "    ${ci_pytest[*]}"
fi

echo
if [[ "$failures" -gt 0 ]]; then
  echo "local_ci: FAILED — $failures gate(s) red. CI will fail on this commit." >&2
  exit 1
fi

if [[ "$lint_only" -eq 1 ]]; then
  echo "local_ci: lint gates passed (partial — test gate skipped)."
else
  echo "local_ci: all gates passed on Python $venv_version."
  # Derived from the guarded matrix, never hardcoded: deleting the Windows leg
  # trips the drift guard above, and until then this sentence follows CI.
  extra_legs=""
  for leg in ${ci_include[@]+"${ci_include[@]}"}; do
    extra_legs+=", ${leg% *} (${leg#* })"
  done
  echo "local_ci: CI also runs this set on ${expected_python_versions[*]}${extra_legs}."
fi

# The gates just ran against the working tree; CI runs the committed checkout.
if command -v git >/dev/null 2>&1 && [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  echo "local_ci: NOTE — the working tree is dirty, so this verdict covers the checkout," >&2
  echo "local_ci: not any commit. Untracked files were linted/tested here but CI never sees" >&2
  echo "local_ci: them; uncommitted fixes can likewise hide a red commit." >&2
fi
