"""Tests for agent_sessions.baseline_publish."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.baseline import PROMOTION_BEGIN, PROMOTION_END, global_baseline_header
from agent_sessions.baseline_publish import (
    baseline_publish,
    collect_promoted_rules,
    publish_agent_files,
    render_agent_document,
)
from agent_sessions.config import ArchiveConfig
from tests.test_baseline import _baseline_settings


def _write_promoted_guardrails(repo_root: Path) -> None:
    global_dir = repo_root / "baseline" / "global"
    global_dir.mkdir(parents=True, exist_ok=True)
    blocks = [
        PROMOTION_BEGIN.format(id="guardrail.pr-only-repo-writes"),
        "## PR-Only Repo Writes",
        "",
        "Use PRs for durable repo writes.",
        PROMOTION_END.format(id="guardrail.pr-only-repo-writes"),
        "",
        PROMOTION_BEGIN.format(id="guardrail.handoff-and-resume"),
        "## Handoff And Resume Discipline",
        "",
        "Maintain SESSION_HANDOFF.md for resume.",
        PROMOTION_END.format(id="guardrail.handoff-and-resume"),
        "",
        PROMOTION_BEGIN.format(id="guardrail.tracked-project-docs"),
        "## Tracked Project Docs",
        "",
        "Use PROJECT_DOC_TEMPLATE for substantial work.",
        PROMOTION_END.format(id="guardrail.tracked-project-docs"),
    ]
    content = global_baseline_header("engineering-guardrails.md") + "\n" + "\n".join(blocks) + "\n"
    (global_dir / "engineering-guardrails.md").write_text(content, encoding="utf-8")


class TestCollectPromotedRules:
    def test_collects_from_global_files(self, repo_root: Path) -> None:
        _write_promoted_guardrails(repo_root)
        settings = _baseline_settings(repo_root)
        rules = collect_promoted_rules(settings)
        assert len(rules) == 3
        assert {rule.rule_id for rule in rules} == {
            "guardrail.pr-only-repo-writes",
            "guardrail.handoff-and-resume",
            "guardrail.tracked-project-docs",
        }


class TestPublishAgentFiles:
    def test_renders_all_agent_targets(self, repo_root: Path) -> None:
        _write_promoted_guardrails(repo_root)
        settings = _baseline_settings(repo_root)
        outputs = publish_agent_files(settings, generated_at="2026-07-06")
        assert len(outputs) == 3
        claude_path = settings.root / "agents" / "claude" / "CLAUDE.generated.md"
        assert claude_path in outputs
        claude_text = outputs[claude_path]
        assert "baseline:generated:begin" in claude_text
        assert claude_text.count("### ") >= 3

    def test_generated_slices_exclude_global_promotion_markers(self, repo_root: Path) -> None:
        _write_promoted_guardrails(repo_root)
        settings = _baseline_settings(repo_root)
        outputs = publish_agent_files(settings, generated_at="2026-07-06")
        claude_text = outputs[settings.root / "agents" / "claude" / "CLAUDE.generated.md"]
        assert "baseline:generated:begin" in claude_text
        assert "baseline:generated:end" in claude_text
        assert "baseline:begin id=" not in claude_text
        assert "baseline:end id=" not in claude_text

    def test_render_agent_document_empty(self) -> None:
        text = render_agent_document("claude", [], "2026-07-06")
        assert "No promoted guardrails found" in text


class TestBaselinePublish:
    def test_writes_generated_files(self, repo_root: Path) -> None:
        _write_promoted_guardrails(repo_root)
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_publish(config, agents=("claude",))
        assert result == 0
        generated = repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md"
        assert generated.exists()
        text = generated.read_text(encoding="utf-8")
        assert "guardrail.pr-only-repo-writes" in text
        assert len(text.splitlines()) > 20

    def test_dry_run(self, repo_root: Path) -> None:
        _write_promoted_guardrails(repo_root)
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_publish(config, dry_run=True)
        assert result == 0
        assert not (repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md").exists()