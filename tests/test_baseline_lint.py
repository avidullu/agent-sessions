"""Tests for baseline lint checks."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from agent_sessions.baseline_lint import (
    baseline_lint,
    baseline_markdown_files,
    lint_baseline,
    normalize_markdown_link,
    render_lint_report,
    repo_relative,
    resolve_markdown_link,
)
from agent_sessions.config import ArchiveConfig


def _config(repo_root: Path) -> ArchiveConfig:
    return ArchiveConfig(repo_root=repo_root, archive_dir=repo_root / "archive", raw_dir=repo_root / "raw", sources=())


def _write_schema(repo_root: Path) -> None:
    schema = repo_root / "baseline" / "SCHEMA.md"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text("# Schema\n", encoding="utf-8")


def test_missing_schema_is_error(repo_root: Path) -> None:
    findings = lint_baseline(_config(repo_root))
    assert any(finding.rule_id == "W1-schema" and finding.severity == "error" for finding in findings)


def test_path_helpers(repo_root: Path) -> None:
    outside = repo_root.parent / "outside.md"
    assert repo_relative(outside, repo_root) == outside.as_posix()
    assert baseline_markdown_files(repo_root / "missing") == []
    assert normalize_markdown_link("archive/session.md \"title\"") == "archive/session.md"
    assert normalize_markdown_link("<archive/session.md>") == "archive/session.md"
    assert resolve_markdown_link(repo_root / "baseline" / "README.md", "https://example.com", repo_root) is None
    assert resolve_markdown_link(repo_root / "baseline" / "README.md", "#local", repo_root) is None
    assert resolve_markdown_link(repo_root / "baseline" / "README.md", "/baseline/SCHEMA.md", repo_root) == (
        repo_root / "baseline" / "SCHEMA.md"
    )


def test_detects_marker_mismatch_and_duplicate_ids(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "global" / "engineering-guardrails.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# Guardrails\n\n"
        '<!-- baseline:begin id="guardrail.one" -->\n'
        "## One\n"
        '<!-- baseline:end id="guardrail.two" -->\n'
        '<!-- baseline:begin id="guardrail.one" -->\n'
        "## Duplicate\n"
        '<!-- baseline:end id="guardrail.one" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    details = [finding.detail for finding in findings if finding.rule_id == "W1-marker"]
    assert any("does not match" in detail for detail in details)
    assert any("Duplicate generated block id" in detail for detail in details)


def test_detects_end_marker_without_begin(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "global" / "engineering-guardrails.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# Guardrails\n\n"
        '<!-- baseline:end id="guardrail.stray" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    details = [finding.detail for finding in findings if finding.rule_id == "W1-marker"]
    assert any("has no begin marker" in detail for detail in details)


def test_detects_nested_unopened_and_unclosed_markers(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "global" / "engineering-guardrails.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# Guardrails\n\n"
        '<!-- baseline:begin id="guardrail.outer" -->\n'
        '<!-- baseline:begin id="guardrail.inner" -->\n'
        '<!-- baseline:end id="guardrail.stray" -->\n'
        '<!-- baseline:begin id="guardrail.open" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    details = [finding.detail for finding in findings if finding.rule_id == "W1-marker"]
    assert any("Nested marker" in detail for detail in details)
    assert any("does not match" in detail for detail in details)
    assert any("has no end marker" in detail for detail in details)


def test_detects_broken_generated_link(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "projects" / "demo" / "README.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# demo\n\n"
        '<!-- baseline:begin id="knowledge.activity" -->\n'
        "## Activity\n\n"
        "See [missing](archive/missing-session.md).\n"
        '<!-- baseline:end id="knowledge.activity" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    broken = [finding for finding in findings if finding.rule_id == "W2-links"]
    assert len(broken) == 1
    assert broken[0].severity == "error"
    assert "archive/missing-session.md" in broken[0].detail


def test_valid_generated_link_resolves(repo_root: Path) -> None:
    _write_schema(repo_root)
    linked = repo_root / "archive" / "session.md"
    linked.parent.mkdir(parents=True, exist_ok=True)
    linked.write_text("# Session\n", encoding="utf-8")
    page = repo_root / "baseline" / "projects" / "demo" / "README.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# demo\n\n"
        '<!-- baseline:begin id="knowledge.activity" -->\n'
        "## Activity\n\n"
        "See [session](archive/session.md).\n"
        '<!-- baseline:end id="knowledge.activity" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    assert not [finding for finding in findings if finding.rule_id == "W2-links"]


def test_generated_links_skip_external_and_anchor_targets(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "projects" / "demo" / "README.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# demo\n\n"
        '<!-- baseline:begin id="knowledge.activity" -->\n'
        "## Activity\n\n"
        "See [site](https://example.com), [mail](mailto:test@example.com), and [anchor](#local).\n"
        '<!-- baseline:end id="knowledge.activity" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    assert not [finding for finding in findings if finding.rule_id == "W2-links"]


def test_detects_stale_generated_block(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "projects" / "demo" / "README.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# demo\n\n"
        '<!-- baseline:begin id="knowledge.activity" -->\n'
        "## Activity\n\n"
        "**Generated at:** 2026-01-01\n"
        '<!-- baseline:end id="knowledge.activity" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root), stale_days=30, today=dt.date(2026, 7, 7))
    stale = [finding for finding in findings if finding.rule_id == "W3-stale"]
    assert len(stale) == 1
    assert stale[0].severity == "warning"


def test_detects_orphan_project_page(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "projects" / "demo" / "README.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# demo\n\nHuman text.\n", encoding="utf-8")
    findings = lint_baseline(_config(repo_root))
    orphan = [finding for finding in findings if finding.rule_id == "W2-orphan"]
    assert len(orphan) == 1
    assert orphan[0].severity == "warning"


def test_inbound_project_link_suppresses_orphan_warning(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "projects" / "demo" / "README.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# demo\n\nHuman text.\n", encoding="utf-8")
    index = repo_root / "baseline" / "README.md"
    index.write_text("[demo](projects/demo/README.md)\n", encoding="utf-8")
    findings = lint_baseline(_config(repo_root))
    assert not [finding for finding in findings if finding.rule_id == "W2-orphan"]


def test_detects_explicit_contradiction_marker(repo_root: Path) -> None:
    _write_schema(repo_root)
    page = repo_root / "baseline" / "global" / "engineering-guardrails.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# Guardrails\n\n"
        '<!-- baseline:begin id="guardrail.one" -->\n'
        "## One\n\n"
        "CONTRADICTION: conflicts with guardrail.two.\n"
        '<!-- baseline:end id="guardrail.one" -->\n',
        encoding="utf-8",
    )
    findings = lint_baseline(_config(repo_root))
    contradiction = [finding for finding in findings if finding.rule_id == "P6-contradiction"]
    assert len(contradiction) == 1
    assert contradiction[0].severity == "warning"


def test_render_lint_report(repo_root: Path) -> None:
    _write_schema(repo_root)
    report = render_lint_report(lint_baseline(_config(repo_root)))
    assert "# Baseline Lint Report" in report
    assert "- Errors:" in report
    assert "| Rule | Severity | Path | Line | Detail |" in report or "No findings." in report


def test_render_lint_report_no_findings() -> None:
    assert "No findings." in render_lint_report([])


def test_baseline_lint_dry_run_returns_nonzero_on_errors(repo_root: Path) -> None:
    assert baseline_lint(_config(repo_root), dry_run=True) == 1


def test_baseline_lint_writes_report(repo_root: Path) -> None:
    _write_schema(repo_root)
    output = repo_root / "baseline" / "lint-report.md"
    assert baseline_lint(_config(repo_root), output=output) == 0
    assert output.exists()
    assert "Baseline Lint Report" in output.read_text(encoding="utf-8")


def test_baseline_lint_writes_relative_report(repo_root: Path) -> None:
    _write_schema(repo_root)
    assert baseline_lint(_config(repo_root), output=Path("baseline/lint-report.md")) == 0
    assert (repo_root / "baseline" / "lint-report.md").exists()
