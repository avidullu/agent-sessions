# Contributing to Agent Sessions

Thanks for your interest in contributing! This document covers how to set up, test, and submit changes.

## Setup

```bash
git clone https://github.com/avidullu/agent-sessions.git
cd agent-sessions
python3 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]" -c constraints-dev.txt
```

## Gates — run before every push

```bash
./scripts/local_ci.sh
```

This runs the exact same gates as CI: ruff (lint), mypy (type check), pytest (713 tests, ≥92% coverage), and markdown link check. All four must pass.

You can also run gates individually:

```bash
python -m ruff check .              # lint
python -m mypy agent_sessions tools tests  # type check
python -m pytest                    # tests
python -m tools.check_md_links      # markdown link check
```

## Adding a new agent source

Agent sources live in `agent_sessions/sources/`. To add a new one:

1. Create a new file in `agent_sessions/sources/` (e.g., `myagent.py`)
2. Implement a function decorated with `@register("my_agent_kind")` that takes a file path and returns `ExtractedSession`
3. Add a source entry to `config/default_sources.toml` and `sources.example.toml`
4. Add tests in `tests/`
5. Run `./scripts/local_ci.sh`

See existing sources (`claude.py`, `codex.py`, `gemini.py`, `grok.py`, `deepseek.py`) for examples.

## PR workflow

1. Branch from `main` (verify you're up to date: `git fetch && git checkout main && git pull`)
2. Make one coherent change per PR
3. Run `./scripts/local_ci.sh` — all gates must be green
4. Push and open a PR
5. Address review comments, re-run gates, wait for LGTM

## Code conventions

- Python 3.11+ with `from __future__ import annotations`
- Type annotations required (`disallow_untyped_defs = true` in mypy config)
- Ruff lint rules: E4, E7, E9, F, B, I, UP, C4
- Line length: 120 characters
- Docstrings for public functions and modules

## Project structure

```
agent_sessions/     # Python package (CLI, extractors, baseline pipeline)
tools/              # Standalone scripts (agent_archive.py, check_md_links.py)
tests/              # pytest test suite
docs/               # Documentation (tracked projects, guides, contracts)
baseline/           # Baseline data (candidates, evidence, handoffs)
archive/            # Session export artifacts (local-only by default)
config/             # Default configuration files
scripts/            # local_ci.sh, pre-push hook, automation
```

## Questions?

Open an issue or ask in the PR. See also:
- [AGENTS.md](AGENTS.md) — agent working agreement (internal conventions)
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — user onboarding
- [docs/FAQ.md](docs/FAQ.md) — common questions
- [docs/ENGINEERING_BASELINE.md](docs/ENGINEERING_BASELINE.md) — baseline architecture
