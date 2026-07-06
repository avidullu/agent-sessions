"""Tests for agent_sessions.baseline_eval."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.baseline import PROMOTION_BEGIN, PROMOTION_END, global_baseline_header
from agent_sessions.baseline_eval import (
    baseline_eval,
    count_published_rules,
    evaluate_all,
    evaluate_e5_publish,
    evaluate_e6_calibrate,
    render_eval_report,
)
from agent_sessions.config import ArchiveConfig


def _write_sidecar(repo_root: Path) -> None:
    sidecar = repo_root / "baseline" / "candidates" / "2026-07-05-extraction.predictions.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "id": "guardrail.tracked-project-docs",
                        "confidence": 0.99,
                        "evidence": ["98 scanned sessions contain tracked-project-docs signals."],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_promoted_guardrails(repo_root: Path) -> None:
    global_dir = repo_root / "baseline" / "global"
    global_dir.mkdir(parents=True, exist_ok=True)
    block = "\n".join(
        [
            PROMOTION_BEGIN.format(id="guardrail.one"),
            "## One",
            "",
            "Rule one.",
            PROMOTION_END.format(id="guardrail.one"),
        ]
    )
    (global_dir / "engineering-guardrails.md").write_text(
        global_baseline_header("engineering-guardrails.md") + "\n" + block + "\n",
        encoding="utf-8",
    )


class TestBaselineEval:
    def test_evaluate_all_on_minimal_repo(self, repo_root: Path) -> None:
        _write_sidecar(repo_root)
        baseline_toml = repo_root / "config" / "baseline.toml"
        baseline_toml.write_text(
            baseline_toml.read_text(encoding="utf-8")
            + "\n[[calibration_anchors]]\n"
            'kind = "tracked-project-doc"\n'
            'source_repo = "badminton-highlight-indexer"\n'
            'source_path = "docs/PROJECT_DOC_TEMPLATE.md"\n',
            encoding="utf-8",
        )
        (repo_root / "docs").mkdir(parents=True, exist_ok=True)
        (repo_root / "docs" / "BASELINE_LOOP_CLOSURE.md").write_text(
            "# Baseline Loop Closure\n\n## 7. progress tracker\n\n| P0 | x | — | ☑ |\n| P9 | x | — | ☐ |\n",
            encoding="utf-8",
        )
        checks = evaluate_all(repo_root)
        assert len(checks) == 6
        by_id = {check.metric_id: check.status for check in checks}
        assert by_id["E1.detect.tracked-project-template"] == "pass"
        assert by_id["E2.anchor.template-source"] == "pass"
        assert by_id["E3.dogfood.tracked-project-doc"] == "pass"

    def test_e5_ignores_evidence_headings(self, repo_root: Path) -> None:
        claude = repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md"
        claude.parent.mkdir(parents=True, exist_ok=True)
        claude.write_text(
            "\n".join(
                [
                    "# Generated",
                    "",
                    "### Rule One",
                    "**Source:** `baseline/global/engineering-guardrails.md` · **ID:** `guardrail.one`",
                    "",
                    "Rule text.",
                    "### Evidence",
                    "- hit",
                    "",
                    "### Rule Two",
                    "**Source:** `baseline/global/engineering-guardrails.md` · **ID:** `guardrail.two`",
                    "",
                    "Rule text.",
                    "### Evidence",
                    "- hit",
                    "",
                    *["padding"] * 25,
                ]
            ),
            encoding="utf-8",
        )
        assert count_published_rules(claude.read_text(encoding="utf-8")) == 2
        check = evaluate_e5_publish(repo_root)
        assert check.status == "fail"
        assert "rules=2" in check.detail

    def test_e5_passes_with_three_rule_ids(self, repo_root: Path) -> None:
        claude = repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md"
        claude.parent.mkdir(parents=True, exist_ok=True)
        sections = []
        for index in range(3):
            sections.extend(
                [
                    f"### Rule {index}",
                    f"**Source:** `baseline/global/x.md` · **ID:** `guardrail.rule-{index}`",
                    "",
                    "Text.",
                    "### Evidence",
                    "- e",
                    "",
                ]
            )
        claude.write_text("# Generated\n\n" + "\n".join(sections + ["line"] * 25), encoding="utf-8")
        check = evaluate_e5_publish(repo_root)
        assert check.status == "pass"
        assert "3 rules" in check.detail

    def test_e6_passes_with_feedback_example(self, repo_root: Path) -> None:
        feedback = repo_root / "baseline" / "calibration" / "feedback.example.toml"
        feedback.parent.mkdir(parents=True, exist_ok=True)
        real_feedback = Path(__file__).resolve().parents[1] / "baseline" / "calibration" / "feedback.example.toml"
        feedback.write_text(real_feedback.read_text(encoding="utf-8"), encoding="utf-8")
        check = evaluate_e6_calibrate(repo_root)
        assert check.status == "pass"

    def test_render_eval_report(self) -> None:
        from agent_sessions.baseline_eval import EfficacyCheck

        report = render_eval_report(
            [EfficacyCheck("E1", "detect", "pass", "ok"), EfficacyCheck("E2", "anchor", "fail", "missing")]
        )
        assert "E1" in report
        assert "Failed: `1`" in report

    def test_baseline_eval_writes_report(self, repo_root: Path) -> None:
        _write_sidecar(repo_root)
        _write_promoted_guardrails(repo_root)
        claude = repo_root / "baseline" / "agents" / "claude" / "CLAUDE.generated.md"
        claude.parent.mkdir(parents=True, exist_ok=True)
        claude.write_text(
            "\n".join(
                [
                    "# Generated",
                    "",
                    "<!-- baseline:generated:begin -->",
                    "",
                    "### Rule A",
                    "**ID:** `guardrail.a`",
                    "### Rule B",
                    "**ID:** `guardrail.b`",
                    "### Rule C",
                    "**ID:** `guardrail.c`",
                    "",
                    *["line"] * 25,
                    "<!-- baseline:generated:end -->",
                ]
            ),
            encoding="utf-8",
        )
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_eval(config)
        assert result in (0, 1)
        report = repo_root / "baseline" / "calibration" / "efficacy-report.md"
        assert report.exists()