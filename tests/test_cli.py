"""Tests for agent_sessions.cli."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.archive import ExportResult
from agent_sessions.cli import _export_summary_lines, build_parser, main


class TestBuildParser:
    def test_creates_parser(self) -> None:
        parser = build_parser()
        assert parser is not None

    def test_discover_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["discover"])
        assert args.cmd == "discover"
        assert args.samples == 10

    def test_discover_with_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["discover", "--samples", "5", "--write", "report.md"])
        assert args.cmd == "discover"
        assert args.samples == 5
        assert args.write == "report.md"

    def test_export_requires_source_or_all(self) -> None:
        parser = build_parser()
        # parse_args succeeds; validation is in main()
        args = parser.parse_args(["export", "--all"])
        assert args.cmd == "export"
        assert args.all is True

    def test_export_with_all(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["export", "--all"])
        assert args.cmd == "export"
        assert args.all is True
        assert args.pdf is None

    def test_export_with_source(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["export", "--source", "claude", "--source", "codex"])
        assert args.source == ["claude", "codex"]

    def test_export_with_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "export",
                "--all",
                "--limit",
                "100",
                "--pdf",
                "--copy-raw",
                "--dry-run",
            ]
        )
        assert args.limit == 100
        assert args.pdf is True
        assert args.copy_raw is True
        assert args.dry_run is True

    def test_export_no_pdf_override(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["export", "--all", "--no-pdf"])
        assert args.pdf is False

    def test_pdf_requires_source_or_all(self) -> None:
        parser = build_parser()
        # parse_args succeeds; validation is in main()
        args = parser.parse_args(["pdf", "--all"])
        assert args.cmd == "pdf"
        assert args.all is True

    def test_pdf_with_all(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pdf", "--all", "--limit", "10", "--force"])
        assert args.cmd == "pdf"
        assert args.all is True
        assert args.limit == 10
        assert args.force is True

    def test_status(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["status", "--source", "codex", "--json"])
        assert args.cmd == "status"
        assert args.source == ["codex"]
        assert args.json is True

    def test_provenance_sync(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "provenance",
                "--database",
                "state.sqlite3",
                "--forgejo-url",
                "https://forge.example.test",
                "sync",
                "--token-file",
                "token",
                "--repo",
                "Example/project",
                "--pr",
                "7",
            ]
        )
        assert args.cmd == "provenance"
        assert args.provenance_cmd == "sync"
        assert args.pull_numbers == [7]
        assert args.database == Path("state.sqlite3")

    def test_provenance_who(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "provenance",
                "--forgejo-url",
                "https://forge.example.test",
                "who",
                "--repo",
                "Example/project",
                "--pr",
                "7",
                "--json",
            ]
        )
        assert args.provenance_cmd == "who"
        assert args.pull_number == 7
        assert args.json is True

    def test_baseline_scaffold(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "scaffold"])
        assert args.cmd == "baseline"
        assert args.baseline_cmd == "scaffold"

    def test_baseline_scaffold_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "scaffold", "--dry-run"])
        assert args.dry_run is True

    def test_baseline_suggest(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["baseline", "suggest", "--max-sessions", "100", "--dry-run"]
        )
        assert args.baseline_cmd == "suggest"
        assert args.max_sessions == 100
        assert args.dry_run is True

    def test_baseline_calibrate(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["baseline", "calibrate", "--feedback", "fb.toml", "--dry-run"]
        )
        assert args.baseline_cmd == "calibrate"
        assert args.feedback == Path("fb.toml")

    def test_baseline_eval(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "eval", "--dry-run"])
        assert args.baseline_cmd == "eval"
        assert args.dry_run is True

    def test_baseline_lint(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "lint", "--stale-days", "45", "--dry-run"])
        assert args.baseline_cmd == "lint"
        assert args.stale_days == 45
        assert args.dry_run is True

    def test_baseline_suggest_no_calibration(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "suggest", "--no-calibration", "--dry-run"])
        assert args.baseline_cmd == "suggest"
        assert args.no_calibration is True

    def test_baseline_publish(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["baseline", "publish", "--agent", "claude", "--agent", "codex", "--dry-run"]
        )
        assert args.baseline_cmd == "publish"
        assert args.publish_agents == ["claude", "codex"]
        assert args.dry_run is True

    def test_baseline_ingest(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "baseline",
                "ingest",
                "--proposal",
                "baseline/proposals/guardrail.explicit-test-gates.example.json",
                "--dry-run",
            ]
        )
        assert args.baseline_cmd == "ingest"
        assert args.proposal == Path("baseline/proposals/guardrail.explicit-test-gates.example.json")
        assert args.dry_run is True

    def test_baseline_promote(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "baseline",
                "promote",
                "--feedback",
                "baseline/calibration/feedback.example.toml",
                "--id",
                "guardrail.pr-only-repo-writes",
                "--dry-run",
            ]
        )
        assert args.baseline_cmd == "promote"
        assert args.feedback == Path("baseline/calibration/feedback.example.toml")
        assert args.promote_ids == ["guardrail.pr-only-repo-writes"]
        assert args.dry_run is True

    def test_baseline_bundle(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "baseline",
                "bundle",
                "--max-sessions",
                "5",
                "--focus",
                "test",
                "--access-level",
                "repo-read-only",
                "--dry-run",
            ]
        )
        assert args.baseline_cmd == "bundle"
        assert args.max_sessions == 5
        assert args.focus == ["test"]
        assert args.access_level == "repo-read-only"
        assert args.dry_run is True

    def test_baseline_handoffs_audit(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "baseline",
                "handoffs",
                "audit",
                "--stale-days",
                "30",
                "--max-archive-records",
                "10",
                "--dry-run",
            ]
        )
        assert args.baseline_cmd == "handoffs"
        assert args.handoffs_cmd == "audit"
        assert args.stale_days == 30
        assert args.max_archive_records == 10
        assert args.dry_run is True

    def test_baseline_replay_select(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["baseline", "replay", "select", "--kind", "planning", "--limit", "5", "--dry-run"]
        )
        assert args.baseline_cmd == "replay"
        assert args.replay_cmd == "select"
        assert args.kind == "planning"
        assert args.limit == 5
        assert args.dry_run is True

    def test_baseline_replay_redact(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "replay", "redact", "--limit", "3", "--dry-run"])
        assert args.baseline_cmd == "replay"
        assert args.replay_cmd == "redact"
        assert args.limit == 3
        assert args.dry_run is True

    def test_baseline_replay_bundle(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["baseline", "replay", "bundle", "--access-tier", "repo-read-only", "--limit", "2", "--dry-run"]
        )
        assert args.baseline_cmd == "replay"
        assert args.replay_cmd == "bundle"
        assert args.access_tier == "repo-read-only"
        assert args.limit == 2
        assert args.dry_run is True

    def test_baseline_replay_ingest(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["baseline", "replay", "ingest", "--result", "r.json", "--dry-run"])
        assert args.baseline_cmd == "replay"
        assert args.replay_cmd == "ingest"
        assert args.result == Path("r.json")
        assert args.dry_run is True

    def test_baseline_handoffs_index(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "baseline",
                "handoffs",
                "index",
                "--max-archive-records",
                "10",
                "--dry-run",
            ]
        )
        assert args.baseline_cmd == "handoffs"
        assert args.handoffs_cmd == "index"
        assert args.max_archive_records == 10
        assert args.dry_run is True

    def test_baseline_handoffs_proposals(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "baseline",
                "handoffs",
                "proposals",
                "--index",
                "custom-index.jsonl",
                "--output-dir",
                "custom-proposals",
                "--max-records-per-project",
                "3",
                "--dry-run",
            ]
        )
        assert args.baseline_cmd == "handoffs"
        assert args.handoffs_cmd == "proposals"
        assert args.index == Path("custom-index.jsonl")
        assert args.output_dir == Path("custom-proposals")
        assert args.max_records_per_project == 3
        assert args.dry_run is True

    def test_config_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--config", "custom.toml", "discover"])
        assert args.config == Path("custom.toml")

    def test_repo_root_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--repo-root", "archive-root", "discover"])
        assert args.repo_root == Path("archive-root")

    def test_no_subcommand_errors(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


class TestExportSummaryLines:
    def test_dry_run_summary(self) -> None:
        lines = _export_summary_lines(
            ExportResult(exported=0),
            write_pdfs=False,
            track_artifacts=False,
            copy_raw_files=False,
            dry_run=True,
        )

        assert "Exported 0 session files." in lines
        assert "- Dry run only: no archive files were written." in lines

    def test_real_export_summary_names_outputs(self) -> None:
        lines = _export_summary_lines(
            ExportResult(exported=3),
            write_pdfs=True,
            track_artifacts=True,
            copy_raw_files=True,
            dry_run=False,
        )

        assert "- Review `archive/INDEX.md` and `archive/index.jsonl`." in lines
        assert any("Git-tracked archive outputs" in line for line in lines)
        assert "- PDFs are written beside Markdown files when `reportlab` is available." in lines
        assert "- Raw backups, if written, are under ignored `raw/`." in lines
        assert any("baseline scaffold" in line for line in lines)

    def test_real_export_summary_notes_local_only_artifacts(self) -> None:
        lines = _export_summary_lines(
            ExportResult(exported=3),
            write_pdfs=False,
            track_artifacts=False,
            copy_raw_files=False,
            dry_run=False,
        )

        assert any("local-only" in line for line in lines)

    def test_skipped_inventory_and_missing_pdf_summary(self) -> None:
        lines = _export_summary_lines(
            ExportResult(
                exported=2,
                pdf_missing=True,
                skipped_sources=("copilot-vscode-windows-inventory (inventory)",),
            ),
            write_pdfs=True,
            track_artifacts=False,
            copy_raw_files=False,
            dry_run=False,
        )

        assert "Skipped sources without extractors:" in lines
        assert "- copilot-vscode-windows-inventory (inventory)" in lines
        assert "Inventory-only sources are expected until transcript files are available." in lines
        assert any("reportlab is not installed" in line for line in lines)


class TestMain:
    @pytest.fixture(autouse=True)
    def _chdir_repo_root(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(repo_root)

    def test_discover(self, repo_root: Path) -> None:
        # Set up config
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        result = main(["discover", "--samples", "1"])
        assert result == 0

    def test_export_requires_source(self, repo_root: Path) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            main(["export"])

    def test_export_all(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        result = main(["export", "--all", "--dry-run"])
        assert result == 0
        assert "Dry run only" in capsys.readouterr().out

    def test_export_reports_skipped_sources_and_pdf_hint(
        self,
        repo_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )

        def fake_export_sources(*args: object, **kwargs: object) -> ExportResult:
            assert kwargs["write_pdfs"] is True
            return ExportResult(
                exported=1,
                pdf_missing=True,
                skipped_sources=("test-inventory (inventory)",),
            )

        monkeypatch.setattr("agent_sessions.cli.export_sources", fake_export_sources)

        result = main(["export", "--all", "--pdf"])

        output = capsys.readouterr().out
        assert result == 0
        assert "test-inventory (inventory)" in output
        assert "reportlab is not installed" in output
        assert "Inventory-only sources are expected" in output

    def test_export_uses_config_pdf_default(
        self,
        repo_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\nwrite_pdfs = true\n',
            encoding="utf-8",
        )

        def fake_export_sources(*args: object, **kwargs: object) -> ExportResult:
            assert kwargs["write_pdfs"] is True
            return ExportResult(exported=1)

        monkeypatch.setattr("agent_sessions.cli.export_sources", fake_export_sources)

        assert main(["export", "--all"]) == 0

    def test_export_no_pdf_overrides_config_default(
        self,
        repo_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\nwrite_pdfs = true\n',
            encoding="utf-8",
        )

        def fake_export_sources(*args: object, **kwargs: object) -> ExportResult:
            assert kwargs["write_pdfs"] is False
            return ExportResult(exported=1)

        monkeypatch.setattr("agent_sessions.cli.export_sources", fake_export_sources)

        assert main(["export", "--all", "--no-pdf"]) == 0

    def test_pdf_requires_source(self, repo_root: Path) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            main(["pdf"])

    def test_status_main(self, repo_root: Path) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        result = main(["status", "--json"])
        assert result == 0

    def test_baseline_scaffold_main(self, repo_root: Path) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        result = main(["baseline", "scaffold", "--dry-run"])
        assert result == 0

    def test_baseline_suggest_main(self, repo_root: Path) -> None:
        # Set up config and archive index
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        # Create archive index, exist_ok=True
        archive_dir = repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "index.jsonl").write_text(
            '{"source":"s","kind":"k","source_file":"/f","sha256":"a","messages":1,"markdown":"a/s.md","metadata":{}}\n',
            encoding="utf-8",
        )
        (repo_root / "config" / "baseline.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "baseline.toml").write_text(
            '[baseline]\nroot = "baseline"\n',
            encoding="utf-8",
        )
        result = main(["baseline", "suggest", "--max-sessions", "1", "--dry-run"])
        assert result == 0

    def test_unknown_command(self, repo_root: Path) -> None:
        with pytest.raises(SystemExit):
            main(["nonexistent"])


class TestMainBaselineSubcommands:
    """Drive the baseline subcommands end-to-end through main() (TD12)."""

    @pytest.fixture(autouse=True)
    def _setup(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(repo_root)
        cfg = repo_root / "config"
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n', encoding="utf-8"
        )
        (cfg / "baseline.toml").write_text('[baseline]\nroot = "baseline"\n', encoding="utf-8")
        assert main(["baseline", "scaffold"]) == 0
        self.repo_root = repo_root

    def _write_sidecar(self) -> Path:
        sidecar = self.repo_root / "baseline" / "candidates" / "2026-07-05-extraction.predictions.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(
            json.dumps(
                {
                    "run_id": "2026-07-05-extraction",
                    "predictions": [
                        {
                            "id": "guardrail.pr-only-repo-writes",
                            "title": "PR-Only Repo Writes",
                            "category": "repo-governance",
                            "confidence": 0.99,
                            "text": "Use PRs for durable repo writes.",
                            "evidence": ["333 sessions mention repo-governance."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return sidecar

    def _write_feedback(self) -> Path:
        fb = self.repo_root / "baseline" / "calibration" / "feedback.toml"
        fb.parent.mkdir(parents=True, exist_ok=True)
        fb.write_text(
            '[feedback."guardrail.pr-only-repo-writes"]\nverdict = "accept"\nnote = "Promote."\n',
            encoding="utf-8",
        )
        return fb

    def test_eval(self) -> None:
        # A scaffold-only repo fails most gates; eval returns 1 in that case and
        # 0 when all pass. Either way the subcommand dispatches and exits cleanly.
        assert main(["baseline", "eval", "--dry-run"]) in (0, 1)

    def test_lint(self) -> None:
        (self.repo_root / "baseline" / "SCHEMA.md").write_text("# Schema\n", encoding="utf-8")
        assert main(["baseline", "lint", "--dry-run"]) == 0

    def test_publish(self) -> None:
        assert main(["baseline", "publish", "--dry-run"]) == 0

    def test_replay_select(self) -> None:
        archive_dir = self.repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "index.jsonl").write_text(
            '{"source":"s","kind":"k","sha256":"a","messages":1,"markdown":"a/s.md","metadata":{}}\n',
            encoding="utf-8",
        )
        assert main(["baseline", "replay", "select", "--dry-run"]) == 0

    def test_replay_redact(self) -> None:
        manifest = self.repo_root / "baseline" / "replay" / "manifest.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("", encoding="utf-8")
        assert main(["baseline", "replay", "redact", "--dry-run"]) == 0

    def test_replay_bundle(self) -> None:
        manifest = self.repo_root / "baseline" / "replay" / "manifest.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("", encoding="utf-8")
        assert main(["baseline", "replay", "bundle", "--dry-run"]) == 0

    def test_replay_ingest(self) -> None:
        archive_dir = self.repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "index.jsonl").write_text(
            '{"source":"s","sha256":"a","messages":5,"markdown":"a/s.md","metadata":{"session_id":"sid"}}\n',
            encoding="utf-8",
        )
        result = self.repo_root / "result.json"
        result.write_text(
            json.dumps(
                {
                    "replay_of": "sid",
                    "replayer": "x",
                    "rubric_version": "replay-rubric-v1",
                    "claim": "Name explicit rollback steps.",
                    "confidence": 0.7,
                    "recommended_action": "watchlist",
                }
            ),
            encoding="utf-8",
        )
        assert main(["baseline", "replay", "ingest", "--result", str(result), "--dry-run"]) == 0

    def test_bundle(self) -> None:
        archive_dir = self.repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "index.jsonl").write_text(
            '{"source":"s","kind":"k","source_file":"/f","sha256":"a","messages":1,"markdown":"a/s.md","metadata":{}}\n',
            encoding="utf-8",
        )
        assert main(["baseline", "bundle", "--dry-run"]) == 0

    def test_handoffs_audit(self) -> None:
        (self.repo_root / "SESSION_HANDOFF.md").write_text(
            "# Session Handoff\n\n## You Are Here\n\nHere.\n",
            encoding="utf-8",
        )
        assert main(["baseline", "handoffs", "audit", "--dry-run"]) == 0

    def test_handoffs_index(self) -> None:
        archive_dir = self.repo_root / "archive"
        markdown_dir = archive_dir / "codex"
        markdown_dir.mkdir(parents=True, exist_ok=True)
        (markdown_dir / "session.md").write_text(
            "# Session Handoff\n\n## You Are Here\n\nHere.\n\n## Next Steps / Open Threads\n\nNext.\n",
            encoding="utf-8",
        )
        (archive_dir / "index.jsonl").write_text(
            json.dumps(
                {
                    "source": "codex",
                    "kind": "codex",
                    "source_file": "/fake/session.jsonl",
                    "sha256": "abc",
                    "messages": 3,
                    "markdown": "archive/codex/session.md",
                    "metadata": {"session_id": "s1", "project": "Project"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert main(["baseline", "handoffs", "index", "--dry-run"]) == 0

    def test_handoffs_proposals(self) -> None:
        index = self.repo_root / "baseline" / "handoffs" / "index.jsonl"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            json.dumps(
                {
                    "id": "handoff.test",
                    "source_kind": "repo-handoff",
                    "source": "codex",
                    "source_file": "/fake/session.jsonl",
                    "markdown_path": "archive/codex/session.md",
                    "session_id": "s1",
                    "project_raw": "test-pilot",
                    "project_slug": "test-pilot",
                    "sections": ["You Are Here"],
                    "signals": ["session handoff"],
                    "warnings": [],
                    "trace": [{"markdown_path": "archive/codex/session.md", "session_id": "s1"}],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert main(["baseline", "handoffs", "proposals", "--dry-run"]) == 0

    def test_ingest(self) -> None:
        proposal = self.repo_root / "baseline" / "proposals" / "guardrail.test.json"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text(
            json.dumps(
                {
                    "id": "guardrail.test",
                    "title": "Test Guardrail",
                    "scope": "global",
                    "category": "regression-frameworks",
                    "risk": "high",
                    "confidence": 0.8,
                    "approval_mode": "strict",
                    "evidence": ["archive/example/session.md mentions pytest"],
                    "suggested_baseline_text": "Run the gates before claiming done.",
                    "open_questions": [],
                }
            ),
            encoding="utf-8",
        )
        assert main(["baseline", "ingest", "--proposal", str(proposal), "--dry-run"]) == 0

    def test_calibrate(self) -> None:
        sidecar = self._write_sidecar()
        feedback = self._write_feedback()
        assert main(["baseline", "calibrate", "--feedback", str(feedback), "--predictions", str(sidecar), "--dry-run"]) == 0

    def test_promote(self) -> None:
        sidecar = self._write_sidecar()
        feedback = self._write_feedback()
        assert main(["baseline", "promote", "--feedback", str(feedback), "--predictions", str(sidecar), "--dry-run"]) == 0

    def test_calibrate_without_feedback_errors(self) -> None:
        # --feedback is required; argparse must exit non-zero rather than dispatch.
        with pytest.raises(SystemExit):
            main(["baseline", "calibrate", "--dry-run"])

    def test_promote_without_feedback_errors(self) -> None:
        with pytest.raises(SystemExit):
            main(["baseline", "promote", "--dry-run"])
