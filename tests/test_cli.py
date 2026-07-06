"""Tests for agent_sessions.cli."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_sessions.cli import build_parser, main


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

    def test_export_all(self, repo_root: Path) -> None:
        (repo_root / "config" / "default_sources.toml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (repo_root / "config" / "default_sources.toml").write_text(
            '[archive]\narchive_dir = "archive"\nraw_dir = "raw"\n',
            encoding="utf-8",
        )
        result = main(["export", "--all", "--dry-run"])
        assert result == 0

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
