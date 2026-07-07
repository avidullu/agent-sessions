<!--
PROJECT DOC TEMPLATE — copy this file to docs/<YOUR_PLAN>.md and fill it in.
-->

# Test Plan: Agent Sessions (>80% Coverage)

> **Status:** `DONE` · **Owner:** `Agent` · **Created:** `2026-07-06` · **Last updated:** `2026-07-07`
> **Lifecycle:** `DRAFT → IN PROGRESS → DONE → archived`
> **Tracking anchors:** §7 progress tracker is the source of truth.
> **PR:** [#12](https://github.com/avidullu/agent-sessions/pull/12) — re-review requested (91.52% coverage, 275 tests)

---

## 0. TL;DR

The `agent_sessions` package now has broad pytest coverage across archive, extractor, CLI, and baseline workflows. The current full-suite gate is **495 passed** with **97.05%** line coverage. Tests focus on unit-testing pure functions, mocking I/O boundaries (filesystem, subprocess, TOML parsing), and exercising the CLI surface through argparse.

## 1. Problem & goal

**Problem:** Coverage must stay high as baseline replay, promotion, and linting workflows add new write paths. Any refactor, new extractor, or baseline logic change risks silent regressions without targeted tests.

**Goal:** Achieve >80% line coverage via pytest with:
- Pure-function unit tests for models, utils, path_templates, render, config
- I/O-mocked tests for archive, sources (extractors), baseline, baseline_agent
- CLI argument parsing and dispatch tests
- Fixture-based extractor tests using in-memory JSONL data

## 4. Design / architecture

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (temp dirs, sample data, mock configs)
├── test_models.py           # Source, SessionMessage, ExtractedSession
├── test_config.py           # load_config, read_toml, load_source, repo_path, ArchiveConfig
├── test_utils.py            # now_utc, jsonl_objects, text_from_content, session_id_from_name, slugify
├── test_path_templates.py   # PathTemplateContext, resolve, discovery helpers
├── test_render.py           # markdown_for_session, write_pdf, modified_timestamp
├── test_archive.py          # iter_source_files, sha256_file, export_sources, write_indexes,
│                            #   discover_sources, select_sources, copy_raw, pdf_existing, etc.
├── test_baseline.py         # baseline_scaffold, baseline_suggest, build_predictions, confidence,
│                            #   keyword_hits, apply_feedback, render_candidate_report, calibration
├── test_baseline_agent.py   # baseline_bundle, select_records, evidence_record, render_agent_prompt
├── test_baseline_handoffs.py # baseline handoff audit parsing, report rendering, write boundaries
├── test_baseline_ingest.py  # proposal ingest validation, trace references, sidecar writes
├── test_baseline_lint.py    # baseline lint markers, generated links, stale/orphan/contradiction checks
├── test_cli.py              # build_parser, main dispatch, arg validation
├── test_tool_wrapper.py     # tools/agent_archive.py wrapper import path
├── test_registry.py         # register, get_extractor, known_kinds
├── test_claude_extractor.py # claude extract
├── test_codex_extractor.py  # codex extract
├── test_deepseek_extractor.py # deepseek_request_dump extract
├── test_gemini_extractor.py # gemini_antigravity extract
├── test_grok_extractor.py   # grok extract
```

**Key testing strategies:**
- **pure functions** — direct assert
- **filesystem I/O** — `tmp_path` fixture
- **TOML parsing** — `tmp_path` with in-memory TOML content
- **subprocess** — `unittest.mock.patch` on `subprocess.run`
- **CLI** — `argparse` parsing with synthetic argv, `capsys` for output
- **extractors** — `tmp_path` with synthetic JSONL files

## 6. Honest limits — what this does NOT do

- Does NOT test `write_pdf` rendering quality (requires reportlab + visual inspection)
- Does NOT test real WSL path resolution (requires actual WSL environment)
- Does NOT integration-test against real agent stores (Codex, Claude, etc.)
- Tests the `tools/agent_archive.py` wrapper import path, but not every command
  through that wrapper.
- Coverage target is per-module, with lower thresholds acceptable for CLI dispatch (`main()`) and PDF generation (`write_pdf`)

## 7. Deliverables & progress tracker   ⟵ **source of truth**

Legend: ☐ Todo · ◐ In progress · ☑ Done · ⛔ Blocked/gated.

| ID | Deliverable | Depends on | Gated? | Status | Notes |
|----|-------------|-----------|--------|--------|-------|
| T0 | Set up pytest infrastructure (conftest, pyproject.toml) | — | No | ☑ | |
| T1 | `test_models.py` | T0 | No | ☑ | 7 tests, 100% coverage |
| T2 | `test_utils.py` | T0 | No | ☑ | 29 tests, 100% coverage |
| T3 | `test_config.py` | T0 | No | ☑ | 8 tests, 100% coverage |
| T4 | `test_path_templates.py` | T0 | No | ☑ | 18 tests, 100% coverage |
| T5 | `test_render.py` | T0 | No | ☑ | 12 tests, 46% coverage (write_pdf partial) |
| T6 | `test_registry.py` | T0 | No | ☑ | 6 tests, 100% coverage |
| T7 | `test_claude_extractor.py` | T0 | No | ☑ | 7 tests, 100% coverage |
| T8 | `test_codex_extractor.py` | T0 | No | ☑ | 9 tests, 100% coverage |
| T9 | `test_deepseek_extractor.py` | T0 | No | ☑ | 4 tests, 100% coverage |
| T10 | `test_gemini_extractor.py` | T0 | No | ☑ | 7 tests, 100% coverage |
| T11 | `test_grok_extractor.py` | T0 | No | ☑ | 5 tests, 100% coverage |
| T12 | `test_archive.py` | T0 | No | ☑ | 35 tests, archive core logic covered |
| T13 | `test_baseline.py` | T0 | No | ☑ | 79 tests, baseline scaffold/suggest/calibrate/promote/schema/project-page upserts |
| T14 | `test_baseline_agent.py` | T0 | No | ☑ | 19 tests, evidence bundles and schema references |
| T15 | `test_cli.py` | T0 | No | ☑ | 51 tests, CLI parsing + dispatch |
| T16 | `test_baseline_handoffs.py` | T0 | No | ☑ | 36 tests, report-only audit, persistent handoff index/feed behavior, stable feed dates, and generated handoff proposals |
| T17 | `test_baseline_lint.py` | T0 | No | ☑ | 19 tests, marker parsing, generated-link, generated-date, stale, orphan, contradiction, and report behavior |
| T18 | `test_baseline_ingest.py` | T0 | No | ☑ | 30 tests, proposal ingest and trace-reference validation |
| T19 | `test_tool_wrapper.py` | T0 | No | ☑ | 1 test, wrapper import path |
| T20 | `test_baseline_replay.py` | T0 | No | ☑ | 31 tests, replay selection scoring, coding exclusion, kind filter, deterministic manifest, redaction preflight |
| T21 | `test_baseline_redaction.py` | T0 | No | ☑ | 17 tests, fail-closed secret detection, placeholders, valueless deterministic report |
| T22 | Run `pytest --cov` and verify >80% overall | T1–T21 | No | ☑ | **97.15%** (554 passed) |

`test_baseline_replay.py` (T20) also covers K10 `baseline replay bundle`: turn
extraction, redacted packet/rubric/report writes, and fail-closed skip of
secret-bearing sessions.

## 8. Open questions

1. Should we add `pytest-cov` and `pytest` as dev dependencies in a `pyproject.toml`? **Yes** — create `pyproject.toml` with `[project.optional-dependencies]` dev group.
2. Coverage threshold for `cli.py` `main()` function (which does real filesystem I/O)? **Accept 60%+** for dispatch branches; the argparse structure is fully testable.
3. Should `reportlab` be mocked or conditionally tested? **Mocked** — `write_pdf` returns `False` when reportlab is absent, which is the common case.
