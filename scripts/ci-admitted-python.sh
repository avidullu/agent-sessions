#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${GITHUB_PATH:?GITHUB_PATH is required}"
case "$RUNNER_TEMP" in
  /*) ;;
  *) echo 'RUNNER_TEMP must be absolute' >&2; exit 1 ;;
esac
[[ "$RUNNER_TEMP" != *$'\n'* && "$RUNNER_TEMP" != *$'\r'* ]] || exit 1

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo/ci/python-runtime"
sha256sum -c SHA256SUMS >&2
# System Python 3.12+ is only the bootstrap verifier. No selected runtime code
# executes until the pinned verifier, CAS, projection and archive all validate.
runtime="$(python3 -I python_runtime_closure.py install \
  --root /opt/bheemci-deps/python-runtime-v1 \
  --lock python-runtime-lock.json --profile python-runtime-profile.json \
  --into "$RUNNER_TEMP/agent-hub-python")"
[[ "$runtime" == "$RUNNER_TEMP/agent-hub-python/python/bin/python3" ]] || exit 1
printf '%s\n' "${runtime%/*}" >> "$GITHUB_PATH"
printf '%s\n' 'PIP_REQUIRE_VIRTUALENV=true' >> "$GITHUB_ENV"
