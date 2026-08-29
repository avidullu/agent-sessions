# Changelog

All notable changes to the agent-sessions project.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Router-fed VS Code native chat records now use `metadata.model_provider` to
  distinguish Z.AI and other language-model providers from GitHub Copilot.
- **Machine-readable local-export routine discovery** — reports native
  scheduler support and `installable` / `current` / `update_available` /
  `repair_required` state through a versioned JSON contract; managed schedules
  carry a schema marker, and Windows pins a supported Python 3.11+ interpreter.
- **Local Forgejo agent-provenance index** — bounded metadata-only sync into a
  mode-0600 SQLite database, exact actor mapping from a versioned identity
  policy, `who`/`list` queries, and append-only owner/session attestations.
  PR/comment bodies, commit messages, signature payloads, file lists, tokens,
  prompts, and transcripts are excluded.
- **Local-only export + schedule installers** for a single primary archive host:
  - `scripts/local-export.sh` / `scripts/local-export.ps1` — export + status, no git
  - `scripts/install-local-export-schedule.sh` / `.ps1` — user crontab or Windows Task Scheduler
- Docs: two automation modes (local-only vs private catalog sync) in `docs/AUTOMATION.md`,
  Getting Started, FAQ; WSL→Windows `/mnt/c` source examples in `sources.example.toml`

- **`ci-gate` job and `scripts/ci-gate.sh`** — the single honest required check. It
  asserts on `needs.<job>.result`, where `skipped` is distinct from `success`, so a job
  that never ran can no longer pass as one. Branch protection should require `ci-gate`
  and nothing else.
- `tests/test_ci_gate.py` — pins the gate's behaviour and the workflow wiring.
- **SSH fleet collect tracked design** — a PR-sized roadmap for a primary host to
  pull session deltas from allowlisted, host-key-verified SSH remotes, with
  contained private staging and manual exact-approval catalog ship-back.

### Fixed
- Untracked local catalogs cannot be staged by a default `git add -- archive/`; they stay private unless force-added.
- Windows provenance stores now combine ACL hardening and verification in one
  PowerShell process, avoid redundant probes for newly created databases, and
  allow loaded owner machines up to 60 seconds to complete a native ACL check.
- `agent-archive status` no longer reports secondary local paths for an already
  deduplicated logical session as perpetually new. Alias detection uses size
  and tail-digest prefilters before hashing, so unrelated new files retain the
  fast status path.
- Local-only exports now use an atomic, ownership-checked cross-shell lock without
  time-based eviction; PowerShell propagates failed native commands; and installed
  cron commands safely quote paths containing spaces, apostrophes, or percent signs.
- `sources.example.toml`: remove the orphaned top-level `glob`, retain the Z.AI WSL
  inventory example, and clarify Linux / WSL-mounted Windows sections.
- **CI reported native-Windows tests as passing when they never ran.** Forgejo maps a
  skipped job to `success` in the commit-status API. `test-windows` carried
  `if: github.server_url == 'https://github.com'`, and because GitHub Actions is
  disabled on the backup mirror that condition was never true on either forge — so the
  Windows legs executed nowhere while every PR showed
  `CI / test (py 3.11, windows-latest) — success`. The guard's stated premise ("every
  registered Forgejo runner is Linux") was also already false: Forgejo has two
  `windows-latest` runners. The condition is removed and Windows now runs on both forges.
- The Windows job now bootstraps without reusable actions and invokes its selected
  virtual-environment interpreter explicitly, avoiding two runner-specific failures:
  an incompatible action-clone path on one runner and delayed composite-action PATH
  propagation on the other.

### Changed
- CI and release automation now use Python 3.13 only on Linux and Windows.
  The package retains its Python 3.11+ runtime floor for existing routine
  installations, but older interpreters are no longer CI-backed.
- Newly generated `archive/index.jsonl`, `archive/INDEX.md`, and Router sidecar
  metadata are ignored when untracked, keeping public product clones private by
  default. Existing tracked private catalogs continue to stage normally; new
  private catalogs opt in explicitly with `git add -f`.
- The repository development version is now `0.3.0.dev0`, distinct from the
  latest published PyPI release (`0.2.0`), and `agent-archive --version` reports
  the installed package version.
- `scripts/local_ci.sh` drift guard no longer *requires* a GitHub-only job (that rule was
  mandating the false green). It now positively asserts that `ci-gate` exists, carries
  `if: ${{ always() }}`, lists every job in `needs:`, and passes every job's result to the
  assertion — so a new job cannot be added outside the gate. Gate checks are scoped to
  the `ci-gate` block so a decoy `needs:` or `always()` on another job cannot satisfy them.

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
