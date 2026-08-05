# Changelog

All notable changes to the agent-sessions project.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **CI reported native-Windows tests as passing when they never ran.** Forgejo maps a
  skipped job to `success` in the commit-status API. `test-windows` carried
  `if: github.server_url == 'https://github.com'`, and because GitHub Actions is
  disabled on the backup mirror that condition was never true on either forge — so the
  Windows legs executed nowhere while every PR showed
  `CI / test (py 3.11, windows-latest) — success`. The guard's stated premise ("every
  registered Forgejo runner is Linux") was also already false: Forgejo has two
  `windows-latest` runners. The condition is removed and Windows now runs on both forges.

### Added
- **`ci-gate` job and `scripts/ci-gate.sh`** — the single honest required check. It
  asserts on `needs.<job>.result`, where `skipped` is distinct from `success`, so a job
  that never ran can no longer pass as one. Branch protection should require `ci-gate`
  and nothing else.
- `tests/test_ci_gate.py` — pins the gate's behaviour and the workflow wiring.

### Changed
- `scripts/local_ci.sh` drift guard no longer *requires* a GitHub-only job (that rule was
  mandating the false green). It now positively asserts that `ci-gate` exists, carries
  `if: ${{ always() }}`, lists every job in `needs:`, and passes every job's result to the
  assertion — so a new job cannot be added outside the gate.

## [0.2.0] — 2026-07-23

### Added
- **Rules extraction pipeline** — mine concrete imperative rules from sessions (R0–R2)
  - `rule_extractor.py` — role-aware imperative parser with echo tagging (D18)
  - `rule_ledger.py` — tracked, merge-aware, redaction-gated evidence ledger (D17)
  - `rule_clusterer.py` — polarity+topic clustering with contradiction pairs (D19)
- **Markdown link checker** (`tools/check_md_links.py`) — CI guard against broken internal links
- **Public launch tracker** (`docs/archives/PUBLIC_LAUNCH_TRACKER.md`) — open-sourcing plan (DONE / archived 2026-07-30 IST)

### Changed
- Foundation hardening complete (H0–H11): ruff/mypy ratchets, CI matrix, coverage 92→92,
  redaction-v1 path placeholders, doc lifecycle conventions, local_ci.sh drift guard
- CI expanded: Windows legs (3.11/3.12/3.13), link-check job, PII scan gate
- `local_ci.sh` now enforces drift parity with `.github/workflows/ci.yml`

### Fixed
- Redaction-v1 now placeholders home-directory paths preventing PII leaks in tracked catalog files

## [0.1.0] — 2026-07-08

### Added
- Initial release: multi-agent session archive tooling
- Importers for Claude Code, Codex CLI, Gemini Antigravity, Grok, DeepSeek V4
- Markdown + PDF export via `agent-archive export --all`
- Archive catalog: `archive/index.jsonl` + `archive/INDEX.md`
- Router sidecar merge: `archive/.router-index.jsonl` → unified catalog
- Baseline pipeline: `baseline suggest` → `promote` → `publish`
- Cross-machine handoff index pattern
- OUTPUT_CONTRACT v1 for feeder tool compatibility
- CI: ruff, mypy, pytest with coverage on Linux + Windows
