"""Tests for agent_sessions.baseline_eval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_sessions.baseline import PROMOTION_BEGIN, PROMOTION_END, global_baseline_header
from agent_sessions.baseline_eval import (
    EfficacyCheck,
    baseline_eval,
    count_published_rules,
    evaluate_all,
    evaluate_e1_detect,
    evaluate_e3_dogfood,
    evaluate_e4_promote,
    evaluate_e5_publish,
    evaluate_e6_calibrate,
    evaluate_extended_gates,
    render_eval_report,
)
from agent_sessions.baseline_types import Prediction
from agent_sessions.config import ArchiveConfig


def _config(repo_root: Path) -> ArchiveConfig:
    return ArchiveConfig(
        repo_root=repo_root,
        archive_dir=repo_root / "archive",
        raw_dir=repo_root / "raw",
        sources=(),
    )


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
        checks = evaluate_all(_config(repo_root))
        assert len(checks) == 16  # 6 E-gates + 10 W/H/R/governance gates (K12)
        by_id = {check.metric_id: check.status for check in checks}
        assert by_id["E1.detect.tracked-project-template"] == "pass"
        assert by_id["E2.anchor.template-source"] == "pass"
        assert by_id["E3.dogfood.tracked-project-doc"] == "pass"
        # K12 gates present; replay gates are `gated` with no replay data in a minimal repo.
        assert by_id["R1-select"] == "gated"
        assert by_id["R3-signal"] == "gated"
        assert by_id["G-no-autopromote"] == "pass"

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
        check = evaluate_e5_publish(_config(repo_root))
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
        check = evaluate_e5_publish(_config(repo_root))
        assert check.status == "pass"
        assert "3 rules" in check.detail

    def test_e6_passes_with_feedback_example(self, repo_root: Path) -> None:
        feedback = repo_root / "baseline" / "calibration" / "feedback.example.toml"
        feedback.parent.mkdir(parents=True, exist_ok=True)
        real_feedback = Path(__file__).resolve().parents[1] / "baseline" / "calibration" / "feedback.example.toml"
        feedback.write_text(real_feedback.read_text(encoding="utf-8"), encoding="utf-8")
        check = evaluate_e6_calibrate(_config(repo_root))
        assert check.status == "pass"

    def test_e1_failures(self, repo_root: Path) -> None:
        check = evaluate_e1_detect(_config(repo_root))
        assert check.status == "fail"
        assert "No prediction sidecar" in check.detail

        sidecar = repo_root / "baseline" / "candidates" / "x.predictions.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps({"predictions": [{"id": "other", "confidence": 0.5, "evidence": ["e"]}]}), encoding="utf-8")
        check = evaluate_e1_detect(_config(repo_root))
        assert "Missing guardrail.tracked-project-docs" in check.detail

        sidecar.write_text(
            json.dumps({"predictions": [{"id": "guardrail.tracked-project-docs", "confidence": 0.9, "evidence": []}]}),
            encoding="utf-8",
        )
        check = evaluate_e1_detect(_config(repo_root))
        assert "no evidence" in check.detail.lower()

    def test_e3_and_e4_failures(self, repo_root: Path) -> None:
        check = evaluate_e3_dogfood(_config(repo_root))
        assert check.status == "fail"

        doc = repo_root / "docs" / "BASELINE_LOOP_CLOSURE.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# Tracker\n\nprogress tracker\n\n| P0 | x |\n", encoding="utf-8")
        check = evaluate_e3_dogfood(_config(repo_root))
        assert check.status == "fail"
        assert "P-numbered tracker rows" in check.detail

        check = evaluate_e4_promote(_config(repo_root))
        assert check.status == "fail"

        global_dir = repo_root / "baseline" / "global"
        global_dir.mkdir(parents=True, exist_ok=True)
        from agent_sessions.baseline import PROMOTED_PLACEHOLDER, global_baseline_header

        (global_dir / "engineering-guardrails.md").write_text(
            global_baseline_header("engineering-guardrails.md") + f"\n{PROMOTED_PLACEHOLDER}\n",
            encoding="utf-8",
        )
        check = evaluate_e4_promote(_config(repo_root))
        assert "placeholder" in check.detail.lower()

    def test_e6_reports_ledger_confidence_adjustments(self, repo_root: Path) -> None:
        feedback = repo_root / "baseline" / "calibration" / "feedback.example.toml"
        feedback.parent.mkdir(parents=True, exist_ok=True)
        real_feedback = Path(__file__).resolve().parents[1] / "baseline" / "calibration" / "feedback.example.toml"
        feedback.write_text(real_feedback.read_text(encoding="utf-8"), encoding="utf-8")
        ledger = repo_root / "baseline" / "metacognition" / "prediction-ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(
            json.dumps(
                {
                    "id": "guardrail.pr-only-repo-writes",
                    "status": "accepted-feedback",
                    "confidence": 0.9,
                }
            )
            + "\n"
            + json.dumps(
                {
                    "id": "guardrail.pr-only-repo-writes",
                    "status": "accepted-feedback",
                    "confidence": 0.92,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        check = evaluate_e6_calibrate(_config(repo_root))
        assert check.status == "pass"
        assert "confidence adjustments" in check.detail
        assert not check.detail.endswith("0 confidence adjustments.")

    def test_e6_fails_without_feedback_file(self, repo_root: Path) -> None:
        check = evaluate_e6_calibrate(_config(repo_root))
        assert check.status == "fail"
        assert "feedback.example.toml missing" in check.detail

    def test_e6_failure_paths(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feedback = repo_root / "baseline" / "calibration" / "feedback.example.toml"
        feedback.parent.mkdir(parents=True, exist_ok=True)
        real_feedback = Path(__file__).resolve().parents[1] / "baseline" / "calibration" / "feedback.example.toml"
        feedback.write_text(real_feedback.read_text(encoding="utf-8"), encoding="utf-8")

        def identity_loop(
            predictions: list[Prediction],
            feedback_map: dict[str, dict[str, str]],
            ledger_entries: list[dict[str, Any]],
        ) -> list[Prediction]:
            return list(predictions)

        monkeypatch.setattr("agent_sessions.baseline_eval.apply_calibration_loop", identity_loop)
        check = evaluate_e6_calibrate(_config(repo_root))
        assert check.status == "fail"
        assert "Rejected ids not suppressed" in check.detail

        monkeypatch.setattr("agent_sessions.baseline_eval.apply_calibration_loop", lambda *args: [])
        check = evaluate_e6_calibrate(_config(repo_root))
        assert check.status == "fail"
        assert "Accepted ids missing" in check.detail

        def static_loop(
            predictions: list[Prediction],
            feedback_map: dict[str, dict[str, str]],
            ledger_entries: list[dict[str, Any]],
        ) -> list[Prediction]:
            from dataclasses import replace

            from agent_sessions.baseline_calibration import should_suppress_prediction, summarize_ledger

            summaries = summarize_ledger(ledger_entries)
            kept: list[Prediction] = []
            for prediction in predictions:
                if should_suppress_prediction(prediction, feedback_map, summaries.get(prediction.id)):
                    continue
                kept.append(replace(prediction, feedback="none"))
            return kept

        monkeypatch.setattr("agent_sessions.baseline_eval.apply_calibration_loop", static_loop)
        check = evaluate_e6_calibrate(_config(repo_root))
        assert check.status == "fail"
        assert "No confidence/feedback movement" in check.detail

    def test_render_eval_report(self) -> None:
        report = render_eval_report(
            [
                EfficacyCheck("E1", "detect", "pass", "ok"),
                EfficacyCheck("E2", "anchor", "fail", "missing"),
                EfficacyCheck("R3", "replay", "gated", "pending"),
            ]
        )
        assert "E1" in report
        assert "Failed: `1`" in report
        assert "Gated (prerequisite pending): `1`" in report


class TestExtendedGates:
    def _config(self, repo_root: Path) -> ArchiveConfig:
        return _config(repo_root)

    def test_r5_safety_passes_with_gitignore_and_scanner(self, repo_root: Path) -> None:
        (repo_root / ".gitignore").write_text("baseline/replay/bundles/\n", encoding="utf-8")
        by_id = {c.metric_id: c for c in evaluate_extended_gates(self._config(repo_root))}
        assert by_id["R5-safety"].status == "pass"

    def test_r5_safety_fails_without_gitignore(self, repo_root: Path) -> None:
        by_id = {c.metric_id: c for c in evaluate_extended_gates(self._config(repo_root))}
        assert by_id["R5-safety"].status == "fail"

    def test_replay_gates_pass_with_data(self, repo_root: Path) -> None:
        replay = repo_root / "baseline" / "replay"
        replay.mkdir(parents=True, exist_ok=True)
        (replay / "manifest.jsonl").write_text(
            json.dumps({"id": "replay.aaa", "selected": True}) + "\n", encoding="utf-8"
        )
        (replay / "ledger.jsonl").write_text(
            json.dumps({"id": "r1", "proposal_id": "replay.aaa", "resolved": True}) + "\n", encoding="utf-8"
        )
        by_id = {c.metric_id: c for c in evaluate_extended_gates(self._config(repo_root))}
        assert by_id["R1-select"].status == "pass"
        assert by_id["R2-dedup"].status == "pass"
        assert by_id["R3-signal"].status == "pass"

    def test_r2_dedup_fails_on_duplicate_ids(self, repo_root: Path) -> None:
        replay = repo_root / "baseline" / "replay"
        replay.mkdir(parents=True, exist_ok=True)
        (replay / "manifest.jsonl").write_text(
            json.dumps({"id": "dup", "selected": True}) + "\n" + json.dumps({"id": "dup", "selected": False}) + "\n",
            encoding="utf-8",
        )
        by_id = {c.metric_id: c for c in evaluate_extended_gates(self._config(repo_root))}
        assert by_id["R2-dedup"].status == "fail"

    def test_no_autopromote_gate_fails_on_offending_proposal(self, repo_root: Path) -> None:
        proposals = repo_root / "baseline" / "proposals"
        proposals.mkdir(parents=True, exist_ok=True)
        (proposals / "bad.json").write_text(json.dumps({"approval_mode": "auto-promote"}), encoding="utf-8")
        by_id = {c.metric_id: c for c in evaluate_extended_gates(self._config(repo_root))}
        assert by_id["G-no-autopromote"].status == "fail"

    def test_baseline_eval_dry_run_and_failure_exit(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _write_sidecar(repo_root)
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_eval(config, dry_run=True)
        assert result == 1
        captured = capsys.readouterr()
        assert "Baseline Efficacy Evaluation" in captured.out

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

    def test_baseline_eval_reports_failures(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_eval(config, output=repo_root / "baseline" / "calibration" / "custom-report.md")
        assert result == 1
        captured = capsys.readouterr()
        assert "Efficacy evaluation failed" in captured.out
        assert (repo_root / "baseline" / "calibration" / "custom-report.md").exists()