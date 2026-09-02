#!/usr/bin/env bash
set -euo pipefail

# setup-python installs into RUNNER_TOOL_CACHE (default /opt/hostedtoolcache).
# Self-hosted Forgejo Linux runners sometimes remount that path read-only, so the
# action fails with `mkdir: cannot create directory ‘/opt/hostedtoolcache/Python’:
# Read-only file system` before any repo gate runs. Measured 2026-09-03 on
# ci-heavy and ci-light for agent-sessions #169. Point both env names the action
# consults at a job-private temp directory. Must run before setup-python.
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"

cache="${RUNNER_TEMP}/hostedtoolcache"
mkdir -p "$cache"
{
  echo "AGENT_TOOLSDIRECTORY=${cache}"
  echo "RUNNER_TOOL_CACHE=${cache}"
} >> "$GITHUB_ENV"
