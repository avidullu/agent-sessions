# Product direction and code map

## North star

**Help a developer carry useful, verifiable lessons between coding sessions and
agents, without losing ownership of their history or instructions.**

The first promise is dependable capture: install, find a session, export a
readable local artifact, and know whether collection is working. The next is
reviewable learning: show a small lesson with evidence and let its owner decide
whether to keep it. More importers and more archived bytes are inputs, not the
measure of success.

This direction preserves the accepted [product boundary](XDSYNC_BOUNDARY.md).
The hub is not a second instruction store, universal memory service, or cloud
transcript collector. Router captures VS Code sessions; the hub archives and
proposes; an owner-chosen control plane owns durable instructions and memory.

## What works, and what remains

| User outcome | Current capability | Limit / next proof |
| --- | --- | --- |
| First useful archive | Packaged `init`, discovery, export, router ingestion | Preserve the fresh-installed-wheel journey on Linux and Windows |
| Understand collection | Hub collection health and router collection status | Unknown timestamps stay unknown; hub cannot infer a live VS Code watcher |
| Review a lesson | Baseline suggestions, feedback, local promotion and generated views | Existing local baseline promotion is not the future attested write into external memory |
| Resume with trusted continuity | Owner-managed instructions and memory remain separate | The source-digest-bound, owner-attested single-host bridge in issue #149 is not shipped |
| Broader collection and synthesis | Collector/session-intel design exists | Designs and prototype commands are not proof of a production continuous collector |

## How to judge progress

Use explicit, local tests and owner feedback, not background telemetry:

- **Time to first useful archive:** can a fresh install produce a readable
  user/assistant exchange and understandable health without cloning this repo?
- **Collection correctness:** do supported fixtures retain messages, provider
  attribution and stable identity without duplicate or missing artifacts?
- **Lesson usefulness:** which proposed lessons did the owner accept, edit or
  reject, and did accepted guidance help in a later session?
- **Trust:** every durable promotion is intentional, evidence-linked and
  inspectable; no raw transcript upload or silent instruction rewrite.

These are evaluation criteria, not claims that adoption or efficacy has already
been measured. Numerical product targets should follow a small real-user pilot.

## Code map

Follow the user journey when choosing a change; do not move stable modules just
to make the directory tree look different.

| Responsibility | Starting points | Verification |
| --- | --- | --- |
| CLI and private workspace setup | `agent_sessions/cli.py`, `onboarding.py`, `config.py`, packaged `default_sources.toml` | `tests/test_installed_wheel.py`, config/CLI tests |
| Provider input and normalization | `agent_sessions/sources/`, `models.py` | Provider fixtures and extractor tests |
| Archive and collection health | `agent_sessions/archive.py`, `archive_status.py`, `collection_health.py` | Archive/status tests and router handoff journey |
| Reviewable baseline learning | `agent_sessions/baseline*.py`, `rule_ledger.py` | Suggest/promote/publish/calibration tests |
| Optional copilot and attribution | `agent_sessions/copilot*.py`, `provenance*.py` | Their isolated contract and privacy tests |
| Operator wrappers | `scripts/`, `tools/` | Scheduler, wrapper and gate tests |
| CI-only admitted toolchain | `ci/python-runtime/`, `scripts/ci-admitted-python.sh` | Pinned checksums, upstream canary, CI bootstrap tests |
| Website and integrations | `site/`, `plugins/` | Keep product claims aligned with shipped behavior |

The installed package belongs in `agent_sessions/`; command wrappers should stay
thin. New provider-specific parsing belongs in `sources/`, not in the CLI.
Extract shared helpers only when fixtures prove the providers have the same
semantics. Private archives, catalogs and operator configuration are runtime
data, not product source.

## Next slices

1. Keep onboarding, health and release integrity dependable. Document the
   existing baseline journey so users can reach a reviewed lesson today.
2. Specify and test the single-host attested handoff bridge (#149) before
   implementing external-memory writes. Agree on exact source binding,
   destination ownership, stale evidence and concurrent-edit behavior first.
3. Build the collector in small slices from its existing design. Avoid mixing
   SSH fleet rollout or hosted-chat adapters into the first local slice.
4. Decompose high-complexity functions (#95) or shared extractors (#94) only in
   behavior-preserving PRs tied to the next feature's needs.

The [roadmap](ROADMAP.md) links the detailed plans. The historical launch tracker
records what shipped in July; it is not a current product completion score.
