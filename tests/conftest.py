"""Shared test fixtures for agent_sessions tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_sessions.config import ArchiveConfig
from agent_sessions.models import Source


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Temporary repo root with minimal structure."""
    (tmp_path / "archive").mkdir(exist_ok=True)
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "baseline" / "candidates").mkdir(parents=True, exist_ok=True)
    (tmp_path / "baseline" / "calibration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "baseline" / "metacognition").mkdir(parents=True, exist_ok=True)
    (tmp_path / "baseline" / "global").mkdir(parents=True, exist_ok=True)
    (tmp_path / "baseline" / "agents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "baseline" / "projects").mkdir(parents=True, exist_ok=True)

    # Write a baseline config
    baseline_toml = tmp_path / "config" / "baseline.toml"
    baseline_toml.write_text(
        '[baseline]\nroot = "baseline"\ncandidates_dir = "baseline/candidates"\n'
        'metacognition_dir = "baseline/metacognition"\n'
        'ledger_path = "baseline/metacognition/prediction-ledger.jsonl"\n'
        'feedback_example = "baseline/calibration/feedback.example.toml"\n\n'
        '[[pilots]]\nslug = "test-pilot"\nkind = "repo"\naliases = ["test-pilot", "tp"]\nnotes = "Test pilot."\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def minimal_sources_toml(repo_root: Path) -> Path:
    """Write a minimal sources.toml for testing."""
    path = repo_root / "sources.toml"
    path.write_text(
        '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n\n'
        '[[sources]]\nname = "test-claude"\nkind = "claude"\n'
        'roots = ["{home}/.claude/projects"]\nglob = "**/*.jsonl"\n\n'
        '[[sources]]\nname = "test-codex"\nkind = "codex"\n'
        'roots = ["{home}/.codex/sessions"]\nglob = "**/*.jsonl"\n',
        encoding="utf-8",
    )
    return path


@pytest.fixture
def archive_config(repo_root: Path) -> ArchiveConfig:
    """Minimal ArchiveConfig for testing."""
    sources = (
        Source(
            name="test-claude",
            kind="claude",
            roots=(repo_root / "sessions" / "claude",),
            glob="**/*.jsonl",
            description="Test Claude source.",
        ),
    )
    return ArchiveConfig(
        repo_root=repo_root,
        archive_dir=repo_root / "archive",
        raw_dir=repo_root / "raw",
        sources=sources,
    )


@pytest.fixture
def multi_source_config(repo_root: Path) -> ArchiveConfig:
    """ArchiveConfig with multiple sources for testing."""
    sources = (
        Source(
            name="test-claude",
            kind="claude",
            roots=(repo_root / "sessions" / "claude",),
            glob="**/*.jsonl",
        ),
        Source(
            name="test-codex",
            kind="codex",
            roots=(repo_root / "sessions" / "codex",),
            glob="**/*.jsonl",
        ),
        Source(
            name="test-inventory",
            kind="inventory",
            roots=(repo_root / "sessions" / "inventory",),
            glob="**/*",
        ),
    )
    return ArchiveConfig(
        repo_root=repo_root,
        archive_dir=repo_root / "archive",
        raw_dir=repo_root / "raw",
        sources=sources,
    )


@pytest.fixture
def sample_claude_jsonl() -> str:
    """Sample Claude Code JSONL session data."""
    lines = [
        json.dumps(
            {
                "sessionId": "abc-123",
                "message": {"role": "user", "content": [{"text": "Hello, Claude!"}]},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ),
        json.dumps(
            {
                "sessionId": "abc-123",
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello! How can I help?"}],
                },
                "timestamp": "2026-01-01T00:00:01Z",
            }
        ),
        json.dumps(
            {
                "sessionId": "abc-123",
                "type": "summary",
                "content": "Session summary text.",
                "timestamp": "2026-01-01T00:00:02Z",
            }
        ),
        json.dumps(
            {
                "sessionId": "abc-123",
                "type": "tool_use",
                "message": {"role": "tool", "content": "Tool output text."},
            }
        ),
        "",
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_codex_jsonl() -> str:
    """Sample Codex JSONL session data."""
    lines = [
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "session_id": "codex-456",
                    "cwd": "/home/user/project",
                    "model_provider": "openai",
                    "cli_version": "1.0.0",
                    "source": "codex",
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ),
        json.dumps(
            {
                "type": "message",
                "payload": {"role": "user", "content": [{"text": "Write a function."}]},
                "timestamp": "2026-01-01T00:00:01Z",
            }
        ),
        json.dumps(
            {
                "type": "message",
                "payload": {
                    "role": "assistant",
                    "content": [{"text": "Here is the function."}],
                },
                "timestamp": "2026-01-01T00:00:02Z",
            }
        ),
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_gemini_jsonl() -> str:
    """Sample Gemini Antigravity JSONL session data."""
    lines = [
        json.dumps(
            {
                "source": "user",
                "content": [{"text": "Hello Gemini!"}],
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        json.dumps(
            {
                "source": "model",
                "content": [{"text": "Hello! How can I assist?"}],
                "created_at": "2026-01-01T00:00:01Z",
            }
        ),
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_grok_jsonl() -> str:
    """Sample Grok JSONL session data."""
    lines = [
        json.dumps(
            {
                "type": "user",
                "content": [{"text": "Hello Grok!"}],
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "content": [{"text": "Hello! What's up?"}],
                "timestamp": "2026-01-01T00:00:01Z",
            }
        ),
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_deepseek_text() -> str:
    """Sample DeepSeek request dump text."""
    return '{"model": "deepseek-v4", "messages": [{"role": "user", "content": "Write code."}]}'


@pytest.fixture
def sample_index_records() -> list[dict]:
    """Sample index records for baseline testing."""
    return [
        {
            "source": "test-claude",
            "kind": "claude",
            "source_file": "/fake/path/session1.jsonl",
            "sha256": "abc123",
            "messages": 5,
            "markdown": "archive/test-claude/session1.md",
            "metadata": {"session_id": "sess-1"},
        },
        {
            "source": "test-codex",
            "kind": "codex",
            "source_file": "/fake/path/session2.jsonl",
            "sha256": "def456",
            "messages": 10,
            "markdown": "archive/test-codex/session2.md",
            "metadata": {"session_id": "sess-2", "cwd": "/home/test"},
        },
        {
            "source": "test-claude",
            "kind": "claude",
            "source_file": "/fake/path/session3.jsonl",
            "sha256": "ghi789",
            "messages": 3,
            "markdown": "archive/test-claude/session3.md",
            "metadata": {"session_id": "sess-3"},
        },
    ]


@pytest.fixture
def mock_tomllib() -> Iterator[MagicMock]:
    """Patch tomllib to return a controlled config dict."""
    with patch("agent_sessions.config.tomllib", create=True) as mock:
        yield mock
