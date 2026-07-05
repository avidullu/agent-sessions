"""Tests for agent_sessions.baseline."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from agent_sessions.baseline import (
    BaselineSettings,
    Pilot,
    Prediction,
    TextSignal,
    apply_feedback,
    baseline_calibrate,
    baseline_files,
    baseline_readme,
    baseline_scaffold,
    baseline_suggest,
    build_predictions,
    candidates_readme,
    confidence,
    is_relative_to,
    keyword_hits,
    load_baseline_settings,
    load_feedback,
    load_index_records,
    metacognition_readme,
    prediction_to_dict,
    project_evidence,
    project_signal_counts,
    render_calibration_summary,
    render_candidate_report,
    render_id_list,
    render_prediction,
    resolve_prediction_sidecar,
    scan_text_signals,
    signal_confidence,
    signal_evidence,
    upsert_ledger,
    write_prediction_artifacts,
)
from agent_sessions.config import ArchiveConfig


class TestConfidence:
    def test_bounds(self) -> None:
        assert confidence(0.5) == 0.5
        assert confidence(1.5) == 0.99
        assert confidence(-0.5) == 0.01

    def test_within_range(self) -> None:
        result = confidence(0.75)
        assert 0.01 <= result <= 0.99


class TestApplyFeedback:
    def test_accept(self) -> None:
        pred = Prediction(
            id="test",
            title="T",
            scope="global",
            risk="low",
            category="meta",
            confidence=0.5,
            status="proposed",
            evidence=[],
            text="t",
        )
        fb = {"test": {"verdict": "accept", "note": "Good."}}
        result = apply_feedback(pred, fb)
        assert result.status == "accepted-feedback"
        assert result.confidence > 0.5

    def test_reject(self) -> None:
        pred = Prediction(
            id="test",
            title="T",
            scope="global",
            risk="low",
            category="meta",
            confidence=0.5,
            status="proposed",
            evidence=[],
            text="t",
        )
        fb = {"test": {"verdict": "reject", "note": "Bad."}}
        result = apply_feedback(pred, fb)
        assert result.status == "rejected-feedback"
        assert result.confidence < 0.5

    def test_edit(self) -> None:
        pred = Prediction(
            id="test",
            title="T",
            scope="global",
            risk="low",
            category="meta",
            confidence=0.5,
            status="proposed",
            evidence=[],
            text="t",
        )
        fb = {"test": {"verdict": "edit", "note": "Fix."}}
        result = apply_feedback(pred, fb)
        assert result.status == "edit-requested"

    def test_no_feedback(self) -> None:
        pred = Prediction(
            id="test",
            title="T",
            scope="global",
            risk="low",
            category="meta",
            confidence=0.5,
            status="proposed",
            evidence=[],
            text="t",
        )
        result = apply_feedback(pred, {})
        assert result.status == "proposed"
        assert result.confidence == 0.5

    def test_unknown_verdict(self) -> None:
        pred = Prediction(
            id="test",
            title="T",
            scope="global",
            risk="low",
            category="meta",
            confidence=0.5,
            status="proposed",
            evidence=[],
            text="t",
        )
        fb = {"test": {"verdict": "unknown", "note": "?"}}
        result = apply_feedback(pred, fb)
        assert result.feedback != "none"


class TestPredictionToDict:
    def test_full_prediction(self) -> None:
        pred = Prediction(
            id="p1",
            title="T1",
            scope="global",
            risk="high",
            category="arch",
            confidence=0.75,
            status="proposed",
            evidence=["e1"],
            text="t1",
            feedback="none",
        )
        d = prediction_to_dict(pred)
        assert d["id"] == "p1"
        assert d["title"] == "T1"
        assert d["scope"] == "global"
        assert d["risk"] == "high"
        assert d["category"] == "arch"
        assert d["confidence"] == 0.75
        assert d["evidence"] == ["e1"]


class TestRenderIdList:
    def test_empty(self) -> None:
        assert render_id_list([]) == ["- None"]

    def test_with_values(self) -> None:
        result = render_id_list(["a", "b"])
        assert result == ["- `a`", "- `b`"]


class TestIsRelativeTo:
    def test_relative(self, tmp_path: Path) -> None:
        child = tmp_path / "a" / "b"
        child.mkdir(parents=True)
        assert is_relative_to(child, tmp_path) is True

    def test_not_relative(self, tmp_path: Path) -> None:
        other = tmp_path / "other"
        child = tmp_path / "a"
        child.mkdir()
        other.mkdir()
        assert is_relative_to(child, other) is False


class TestKeywordHits:
    def test_exact_match(self) -> None:
        text = "pull request and merge approval"
        count = keyword_hits(text, ("pull request", "merge", "approval"))
        assert count >= 3

    def test_no_match(self) -> None:
        text = "nothing relevant here"
        count = keyword_hits(text, ("pull request", "merge"))
        assert count == 0

    def test_boundary_match(self) -> None:
        text = "i opened a pr today"
        count = keyword_hits(text, ("pr",))
        assert count >= 1

    def test_case_insensitive(self) -> None:
        text = "pull request and Pull Request"
        count = keyword_hits(text, ("pull request",))
        assert count >= 1


class TestProjectSignalCounts:
    def test_with_hits(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(
                Pilot(slug="test-pilot", kind="repo", aliases=("tp",), notes="Test."),
            ),
        )
        records = [
            {
                "source_file": "/fake/test-pilot/file.jsonl",
                "markdown": "archive/tp/session.md",
                "metadata": {},
            },
        ]
        counts = project_signal_counts(settings, records)
        assert counts["test-pilot"] >= 1

    def test_no_hits(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(
                Pilot(slug="test-pilot", kind="repo", aliases=("tp",), notes="Test."),
            ),
        )
        records = [
            {
                "source_file": "/other/file.jsonl",
                "markdown": "archive/other/session.md",
                "metadata": {},
            }
        ]
        counts = project_signal_counts(settings, records)
        assert counts["test-pilot"] == 0


class TestSignalConfidence:
    def test_no_signals(self) -> None:
        result = signal_confidence({}, "nonexistent", base=0.5)
        assert result == 0.5

    def test_with_signals(self) -> None:
        signals = {"test-group": [TextSignal(source="s", markdown="m.md", count=100)]}
        result = signal_confidence(signals, "test-group", base=0.5)
        assert result > 0.5


class TestSignalEvidence:
    def test_no_signals(self) -> None:
        result = signal_evidence({}, "nonexistent")
        assert len(result) == 1
        assert "No" in result[0]

    def test_with_signals(self) -> None:
        signals = {"test-group": [TextSignal(source="s", markdown="m.md", count=5)]}
        result = signal_evidence(signals, "test-group")
        assert len(result) >= 1


class TestProjectEvidence:
    def test_no_hits(self) -> None:
        result = project_evidence(Counter())
        assert len(result) == 1
        assert "No configured" in result[0]

    def test_with_hits(self) -> None:
        result = project_evidence(Counter({"pilot-a": 5, "pilot-b": 3}))
        assert len(result) == 2
        assert "pilot-a" in result[0]


class TestLoadBaselineSettings:
    def test_loads_from_config(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        settings = load_baseline_settings(config)
        assert isinstance(settings, BaselineSettings)
        assert len(settings.pilots) >= 1

    def test_loads_without_config_file(self, tmp_path: Path) -> None:
        config = ArchiveConfig(
            repo_root=tmp_path,
            archive_dir=tmp_path / "archive",
            raw_dir=tmp_path / "raw",
            sources=(),
        )
        settings = load_baseline_settings(config)
        assert isinstance(settings, BaselineSettings)
        assert settings.pilots == ()


class TestBaselineFiles:
    def test_returns_dict(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(Pilot(slug="test", kind="repo", aliases=(), notes=""),),
        )
        files = baseline_files(settings)
        assert isinstance(files, dict)
        assert len(files) > 0
        # Should include project readme for pilot
        project_readme_path = settings.root / "projects" / "test" / "README.md"
        assert project_readme_path in files


class TestReadmeFunctions:
    def test_baseline_readme(self) -> None:
        text = baseline_readme()
        assert "Engineering Baseline" in text

    def test_candidates_readme(self) -> None:
        text = candidates_readme()
        assert "Baseline Candidates" in text

    def test_metacognition_readme(self) -> None:
        text = metacognition_readme()
        assert "Metacognition" in text


class TestBaselineScaffold:
    def test_dry_run(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_scaffold(config, dry_run=True)
        assert result == 0

    def test_creates_files(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_scaffold(config, dry_run=False)
        assert result == 0
        assert (repo_root / "baseline" / "README.md").exists()
        assert (repo_root / "baseline" / "candidates" / "README.md").exists()


class TestBaselineSuggest:
    def _setup_config(self, repo_root: Path) -> ArchiveConfig:
        """Helper to set up config with test data for baseline suggest."""
        # Create archive index
        archive_dir = repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Create a markdown file that the scanner can read
        md_dir = archive_dir / "test-claude"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / "session.md"
        md_path.write_text(
            "# Test Session\n\nPull request workflow and pytest coverage.\n",
            encoding="utf-8",
        )

        # Write index.jsonl
        index_path = archive_dir / "index.jsonl"
        index_path.write_text(
            json.dumps(
                {
                    "source": "test-claude",
                    "kind": "claude",
                    "source_file": "/fake/s.jsonl",
                    "sha256": "abc123",
                    "messages": 3,
                    "markdown": "archive/test-claude/session.md",
                    "metadata": {"session_id": "s1"},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        return ArchiveConfig(
            repo_root=repo_root,
            archive_dir=archive_dir,
            raw_dir=repo_root / "raw",
            sources=(),
        )

    def test_suggest_dry_run(self, repo_root: Path) -> None:
        config = self._setup_config(repo_root)
        result = baseline_suggest(config, max_sessions=1, dry_run=True)
        assert result == 0

    def test_suggest_writes_output(self, repo_root: Path) -> None:
        config = self._setup_config(repo_root)
        result = baseline_suggest(config, max_sessions=1)
        assert result == 0
        # Check that candidate file was written
        candidates = list(
            (repo_root / "baseline" / "candidates").glob("*-extraction.md")
        )
        assert len(candidates) >= 1

    def test_suggest_with_feedback(self, repo_root: Path) -> None:
        config = self._setup_config(repo_root)

        # Create feedback file
        feedback_dir = repo_root / "baseline" / "calibration"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        feedback_file = feedback_dir / "feedback.toml"
        feedback_file.write_text(
            '[feedback."profile.multi-agent-builder"]\nverdict = "accept"\nnote = "Good."\n',
            encoding="utf-8",
        )

        result = baseline_suggest(config, max_sessions=1, feedback=feedback_file)
        assert result == 0


class TestBuildPredictions:
    def test_returns_predictions(self) -> None:
        predictions = build_predictions(
            source_counts=Counter({"claude": 5, "codex": 3}),
            kind_counts=Counter({"claude": 5, "codex": 3}),
            project_hits=Counter({"test": 2}),
            text_signals={
                "repo-governance": [TextSignal(source="s", markdown="m.md", count=10)]
            },
        )
        assert len(predictions) > 0
        for pred in predictions:
            assert isinstance(pred, Prediction)
            assert pred.id
            assert pred.title


class TestRenderPrediction:
    def test_renders(self) -> None:
        pred = Prediction(
            id="test.id",
            title="Test Prediction",
            scope="global",
            risk="medium",
            category="arch",
            confidence=0.75,
            status="proposed",
            evidence=["Evidence 1"],
            text="Suggested text.",
            feedback="none",
        )
        lines = render_prediction(pred)
        assert isinstance(lines, list)
        assert any("Test Prediction" in line for line in lines)
        assert any("test.id" in line for line in lines)
        assert any("Suggested text." in line for line in lines)


class TestRenderCandidateReport:
    def test_renders_full_report(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(),
        )
        records = [
            {
                "source": "s",
                "kind": "k",
                "source_file": "/f",
                "sha256": "a",
                "messages": 1,
                "markdown": "a/s.md",
                "metadata": {},
            }
        ]
        pred = Prediction(
            id="t",
            title="T",
            scope="g",
            risk="l",
            category="m",
            confidence=0.5,
            status="p",
            evidence=[],
            text="x",
        )
        report = render_candidate_report(
            settings=settings,
            index_records=records,
            source_counts=Counter({"s": 1}),
            kind_counts=Counter({"k": 1}),
            project_hits=Counter(),
            text_signals={},
            predictions=[pred],
            max_sessions=1,
            feedback_path=None,
        )
        assert "Baseline Candidate Extraction" in report


class TestRenderCalibrationSummary:
    def test_renders(self, tmp_path: Path) -> None:
        prediction_data = {
            "run_id": "test-run",
            "generated_at": "2026-01-01T00:00:00Z",
            "scanned_sessions": 10,
            "predictions": [
                {
                    "id": "p1",
                    "title": "P1",
                    "scope": "g",
                    "risk": "l",
                    "category": "m",
                    "confidence": 0.5,
                    "status": "p",
                    "evidence": [],
                    "text": "t",
                },
                {
                    "id": "p2",
                    "title": "P2",
                    "scope": "g",
                    "risk": "l",
                    "category": "m",
                    "confidence": 0.5,
                    "status": "p",
                    "evidence": [],
                    "text": "t",
                },
            ],
        }
        feedback_map = {
            "p1": {"verdict": "accept", "note": "Good."},
            "p2": {"verdict": "reject", "note": "Bad."},
        }
        summary = render_calibration_summary(
            prediction_data=prediction_data,
            feedback_map=feedback_map,
            feedback_path=tmp_path / "feedback.toml",
            prediction_path=tmp_path / "predictions.json",
        )
        assert "Calibration Summary" in summary
        assert "Accepted" in summary
        assert "Rejected" in summary


class TestUpsertLedger:
    def test_writes_ledger(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        predictions = [{"id": "p1", "title": "T1"}]
        upsert_ledger(ledger_path, "run-1", predictions)
        assert ledger_path.exists()
        content = ledger_path.read_text(encoding="utf-8")
        assert "run-1" in content

    def test_replaces_existing_run(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        # First write
        upsert_ledger(ledger_path, "run-1", [{"id": "p1"}])
        # Second write with same run_id should replace
        upsert_ledger(ledger_path, "run-1", [{"id": "p2"}])
        content = ledger_path.read_text(encoding="utf-8")
        assert "p2" in content


class TestWritePredictionArtifacts:
    def test_writes_sidecar_and_ledger(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(),
        )
        candidate_path = settings.candidates_dir / "2026-07-06-extraction.md"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text("dummy", encoding="utf-8")

        pred = Prediction(
            id="p1",
            title="T1",
            scope="g",
            risk="l",
            category="m",
            confidence=0.5,
            status="p",
            evidence=[],
            text="t",
        )
        write_prediction_artifacts(
            settings=settings,
            candidate_path=candidate_path,
            predictions=[pred],
            source_counts=Counter({"s": 1}),
            kind_counts=Counter({"k": 1}),
            project_hits=Counter(),
            scanned_sessions=1,
        )

        sidecar = candidate_path.with_suffix(".predictions.json")
        assert sidecar.exists()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["run_id"] == "2026-07-06-extraction"


class TestResolvePredictionSidecar:
    def test_raises_when_none_found(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(),
        )
        settings.candidates_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(SystemExit, match="No prediction sidecar"):
            resolve_prediction_sidecar(settings, None)

    def test_returns_given_path(self, repo_root: Path) -> None:
        settings = BaselineSettings(
            root=repo_root / "baseline",
            candidates_dir=repo_root / "baseline" / "candidates",
            metacognition_dir=repo_root / "baseline" / "metacognition",
            ledger_path=repo_root / "baseline" / "metacognition" / "ledger.jsonl",
            feedback_example=repo_root
            / "baseline"
            / "calibration"
            / "feedback.example.toml",
            pilots=(),
        )
        sidecar_path = settings.candidates_dir / "test.predictions.json"
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text("{}", encoding="utf-8")

        result = resolve_prediction_sidecar(settings, sidecar_path)
        assert result == sidecar_path


class TestBaselineCalibrate:
    def test_dry_run(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )

        # Create a prediction sidecar
        candidates_dir = repo_root / "baseline" / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)
        sidecar_path = candidates_dir / "test.predictions.json"
        sidecar_path.write_text(
            json.dumps(
                {
                    "run_id": "test",
                    "predictions": [
                        {
                            "id": "p1",
                            "title": "T1",
                            "scope": "g",
                            "risk": "l",
                            "category": "m",
                            "confidence": 0.5,
                            "status": "p",
                            "evidence": [],
                            "text": "t",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        # Create a feedback file
        feedback_dir = repo_root / "baseline" / "calibration"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        feedback_path = feedback_dir / "feedback.toml"
        feedback_path.write_text(
            '[feedback."p1"]\nverdict = "accept"\nnote = "Good."\n',
            encoding="utf-8",
        )

        result = baseline_calibrate(
            config, feedback=feedback_path, predictions=sidecar_path, dry_run=True
        )
        assert result == 0

    def test_missing_feedback_raises(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        fake_feedback = repo_root / "nonexistent.toml"
        with pytest.raises(SystemExit):
            baseline_calibrate(config, feedback=fake_feedback, dry_run=True)


class TestScanTextSignals:
    def test_scans_with_mock(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        # Create a markdown file with keywords
        md_dir = repo_root / "archive" / "test-src"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / "session.md"
        md_path.write_text(
            "# Pull request workflow\n\nUse pytest and ruff before merging.\n",
            encoding="utf-8",
        )

        records = [
            {
                "source": "test-src",
                "kind": "claude",
                "markdown": "archive/test-src/session.md",
            }
        ]
        result = scan_text_signals(config, records, max_sessions=1)
        assert isinstance(result, dict)
        # Should find repo-governance and regression-frameworks signals
        assert any(len(signals) > 0 for signals in result.values()), (
            "Should find at least some keyword signals"
        )


class TestLoadFeedback:
    def test_loads_feedback(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        feedback_dir = repo_root / "baseline" / "calibration"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        fb_path = feedback_dir / "feedback.toml"
        fb_path.write_text(
            '[feedback."test.id"]\nverdict = "accept"\nnote = "Good."\n',
            encoding="utf-8",
        )
        result = load_feedback(config, fb_path)
        assert "test.id" in result
        assert result["test.id"]["verdict"] == "accept"

    def test_no_feedback_file_returns_empty(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = load_feedback(config, None)
        assert result == {}

    def test_nonexistent_feedback_raises(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        with pytest.raises(SystemExit):
            load_feedback(config, repo_root / "nonexistent.toml")


class TestLoadIndexRecordsBaseline:
    def test_loads_from_archive(self, repo_root: Path) -> None:
        # Set up index
        archive_dir = repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        index_path = archive_dir / "index.jsonl"
        index_path.write_text(
            json.dumps(
                {
                    "source": "s",
                    "kind": "k",
                    "source_file": "/f",
                    "sha256": "a",
                    "messages": 1,
                    "markdown": "a/s.md",
                    "metadata": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=archive_dir,
            raw_dir=repo_root / "raw",
            sources=(),
        )
        records = load_index_records(config)
        assert len(records) == 1

    def test_no_index_raises(self, repo_root: Path) -> None:
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        with pytest.raises(SystemExit):
            load_index_records(config)
