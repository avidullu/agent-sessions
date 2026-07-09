"""Command-line interface for the archive tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from .archive import ExportResult, discover_sources, export_sources, pdf_existing, prune_index_records
from .archive_status import archive_status
from .baseline import baseline_scaffold, baseline_suggest
from .config import ArchiveConfig, load_config


def default_repo_root() -> Path:
    return Path.cwd()


def _handle_discover(config: ArchiveConfig, args: argparse.Namespace) -> int:
    return discover_sources(config, samples=args.samples, write=args.write)


def _export_summary_lines(
    result: ExportResult,
    *,
    write_pdfs: bool,
    copy_raw_files: bool,
    dry_run: bool,
) -> list[str]:
    lines = [f"Exported {result.exported} session files."]
    if result.skipped_sources:
        lines.append("Skipped sources without extractors:")
        lines.extend(f"- {source}" for source in result.skipped_sources)
        if any("(inventory)" in source for source in result.skipped_sources):
            lines.append("Inventory-only sources are expected until transcript files are available.")
    if result.pdf_missing:
        lines.append("PDF export requested but reportlab is not installed. Run: python -m pip install reportlab")

    lines.extend(["", "Next steps:"])
    if dry_run:
        lines.append("- Dry run only: no archive files were written.")
    else:
        lines.append("- Review `archive/INDEX.md` and `archive/index.jsonl`.")
        if write_pdfs:
            lines.append("- PDFs are written beside Markdown files when `reportlab` is available.")
        else:
            lines.append("- Markdown files are under `archive/`; rerun with `--pdf` for optional PDFs.")
        if copy_raw_files:
            lines.append("- Raw backups, if written, are under ignored `raw/`.")
        lines.append("- Check intended changes with `git status --short archive/ docs/DISCOVERY.md`.")
        lines.append("- Stage explicit paths only; keep `sources.toml`, `raw/`, and unrelated files out.")
        lines.append("- For baseline review, run `python tools/agent_archive.py baseline scaffold` and `baseline suggest`.")
    return lines


def _handle_export(config: ArchiveConfig, args: argparse.Namespace) -> int:
    if not args.all and not args.source:
        raise SystemExit("export requires --all or at least one --source")
    write_pdfs = config.write_pdfs if args.pdf is None else args.pdf
    result = export_sources(
        config,
        selected=args.source,
        limit=args.limit,
        write_pdfs=write_pdfs,
        copy_raw_files=args.copy_raw,
        dry_run=args.dry_run,
    )
    print(
        "\n".join(
            _export_summary_lines(
                result,
                write_pdfs=write_pdfs,
                copy_raw_files=args.copy_raw,
                dry_run=args.dry_run,
            )
        )
    )
    return 0


def _handle_pdf(config: ArchiveConfig, args: argparse.Namespace) -> int:
    if not args.all and not args.source:
        raise SystemExit("pdf requires --all or at least one --source")
    return pdf_existing(config, selected=args.source, limit=args.limit, force=args.force)


def _handle_status(config: ArchiveConfig, args: argparse.Namespace) -> int:
    return archive_status(config, selected=args.source, as_json=args.json)


def _handle_prune(config: ArchiveConfig, args: argparse.Namespace) -> int:
    return prune_index_records(config, dry_run=args.dry_run)


def _handle_baseline_scaffold(config: ArchiveConfig, args: argparse.Namespace) -> int:
    return baseline_scaffold(config, dry_run=args.dry_run)


def _handle_baseline_suggest(config: ArchiveConfig, args: argparse.Namespace) -> int:
    return baseline_suggest(
        config,
        output=args.output,
        max_sessions=args.max_sessions,
        feedback=args.feedback,
        dry_run=args.dry_run,
        use_calibration=not args.no_calibration,
    )


def _handle_baseline_calibrate(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline import baseline_calibrate

    return baseline_calibrate(
        config,
        feedback=args.feedback,
        predictions=args.predictions,
        output=args.output,
        dry_run=args.dry_run,
    )


def _handle_baseline_promote(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_promote import baseline_promote

    promote_ids = tuple(args.promote_ids) if args.promote_ids else None
    return baseline_promote(
        config,
        feedback=args.feedback,
        predictions=args.predictions,
        dry_run=args.dry_run,
        ids=promote_ids,
    )


def _handle_baseline_publish(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_publish import baseline_publish

    publish_agents = tuple(args.publish_agents) if args.publish_agents else None
    return baseline_publish(config, dry_run=args.dry_run, agents=publish_agents)


def _handle_baseline_eval(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_eval import baseline_eval

    return baseline_eval(config, output=args.output, dry_run=args.dry_run)


def _handle_baseline_lint(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_lint import baseline_lint

    return baseline_lint(config, output=args.output, stale_days=args.stale_days, dry_run=args.dry_run)


def _handle_baseline_ingest(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_ingest import baseline_ingest

    return baseline_ingest(config, proposal=args.proposal, output=args.output, dry_run=args.dry_run)


def _handle_baseline_bundle(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_agent import baseline_bundle

    return baseline_bundle(
        config,
        output_dir=args.output_dir,
        max_sessions=args.max_sessions,
        max_chars_per_session=args.max_chars_per_session,
        access_level=args.access_level,
        focus=args.focus,
        dry_run=args.dry_run,
    )


def _handle_baseline_handoffs_audit(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_handoffs import baseline_handoffs_audit

    return baseline_handoffs_audit(
        config,
        output=args.output,
        stale_days=args.stale_days,
        max_archive_records=args.max_archive_records,
        dry_run=args.dry_run,
    )


def _handle_baseline_handoffs_index(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_handoffs import baseline_handoffs_index

    return baseline_handoffs_index(
        config,
        output=args.output,
        max_archive_records=args.max_archive_records,
        dry_run=args.dry_run,
    )


def _handle_baseline_handoffs_proposals(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_handoffs import baseline_handoffs_proposals

    return baseline_handoffs_proposals(
        config,
        index=args.index,
        output_dir=args.output_dir,
        max_records_per_project=args.max_records_per_project,
        dry_run=args.dry_run,
    )


def _handle_baseline_replay_select(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_replay import baseline_replay_select

    return baseline_replay_select(
        config,
        kind=args.kind,
        limit=args.limit,
        output=args.output,
        max_archive_records=args.max_archive_records,
        dry_run=args.dry_run,
    )


def _handle_baseline_replay_redact(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_replay import baseline_replay_redact

    return baseline_replay_redact(
        config,
        manifest=args.manifest,
        output=args.output,
        limit=args.limit,
        dry_run=args.dry_run,
    )


def _handle_baseline_replay_bundle(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_replay import baseline_replay_bundle

    return baseline_replay_bundle(
        config,
        manifest=args.manifest,
        output_dir=args.output_dir,
        limit=args.limit,
        access_tier=args.access_tier,
        dry_run=args.dry_run,
    )


def _handle_baseline_replay_ingest(config: ArchiveConfig, args: argparse.Namespace) -> int:
    from .baseline_replay_ingest import baseline_replay_ingest

    return baseline_replay_ingest(
        config,
        result=args.result,
        output_dir=args.output_dir,
        ledger=args.ledger,
        dry_run=args.dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export local coding-agent sessions.")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root(), help="Archive repository root.")
    parser.add_argument("--config", type=Path, help="Optional sources TOML path.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_discover = sub.add_parser("discover", help="Discover configured local stores.")
    p_discover.add_argument("--samples", type=int, default=10)
    p_discover.add_argument("--write", help="Write Markdown discovery report to this path.")
    p_discover.set_defaults(func=_handle_discover)

    p_export = sub.add_parser("export", help="Export configured local stores.")
    p_export.add_argument("--all", action="store_true", help="Export all configured sources.")
    p_export.add_argument("--source", action="append", help="Source name or kind to export. Can be repeated.")
    p_export.add_argument("--limit", type=int, help="Maximum files to export, useful for tests.")
    p_pdf_mode = p_export.add_mutually_exclusive_group()
    p_pdf_mode.add_argument(
        "--pdf",
        dest="pdf",
        action="store_true",
        help="Write simple PDFs for this export, overriding archive.write_pdfs.",
    )
    p_pdf_mode.add_argument(
        "--no-pdf",
        dest="pdf",
        action="store_false",
        help="Skip PDFs for this export, overriding archive.write_pdfs.",
    )
    p_export.add_argument("--copy-raw", action="store_true", help="Copy gzip-compressed raw source files to raw/.")
    p_export.add_argument("--dry-run", action="store_true")
    p_export.set_defaults(func=_handle_export, pdf=None)

    p_pdf = sub.add_parser("pdf", help="Generate PDFs from existing archive Markdown.")
    p_pdf.add_argument("--all", action="store_true", help="Generate PDFs for all indexed Markdown files.")
    p_pdf.add_argument("--source", action="append", help="Source name or kind to PDF. Can be repeated.")
    p_pdf.add_argument("--limit", type=int, help="Maximum PDFs to write.")
    p_pdf.add_argument("--force", action="store_true", help="Overwrite existing PDFs.")
    p_pdf.set_defaults(func=_handle_pdf)

    p_status = sub.add_parser("status", help="Show archive freshness and origin summary.")
    p_status.add_argument("--source", action="append", help="Source name or kind to check. Can be repeated.")
    p_status.add_argument("--json", action="store_true", help="Write machine-readable JSON.")
    p_status.set_defaults(func=_handle_status)

    p_prune = sub.add_parser("prune", help="Drop index records whose archive Markdown is missing on disk.")
    p_prune.add_argument("--dry-run", action="store_true", help="Report what would be pruned without writing.")
    p_prune.set_defaults(func=_handle_prune)

    p_baseline = sub.add_parser("baseline", help="Work with engineering baseline candidates.")
    baseline_sub = p_baseline.add_subparsers(dest="baseline_cmd", required=True)

    p_baseline_scaffold = baseline_sub.add_parser("scaffold", help="Create missing baseline folders/templates.")
    p_baseline_scaffold.add_argument("--dry-run", action="store_true")
    p_baseline_scaffold.set_defaults(func=_handle_baseline_scaffold)

    p_baseline_suggest = baseline_sub.add_parser("suggest", help="Generate reviewable baseline candidate suggestions.")
    p_baseline_suggest.add_argument("--output", type=Path, help="Candidate Markdown output path.")
    p_baseline_suggest.add_argument(
        "--max-sessions",
        type=int,
        default=500,
        help="Maximum Markdown sessions to scan for text signals. Use 0 for all indexed sessions.",
    )
    p_baseline_suggest.add_argument("--feedback", type=Path, help="Optional calibration feedback TOML file.")
    p_baseline_suggest.add_argument(
        "--no-calibration",
        action="store_true",
        help="Skip ledger-aware calibration filtering and confidence adjustments.",
    )
    p_baseline_suggest.add_argument("--dry-run", action="store_true")
    p_baseline_suggest.set_defaults(func=_handle_baseline_suggest)

    p_baseline_calibrate = baseline_sub.add_parser("calibrate", help="Summarize calibration feedback for predictions.")
    p_baseline_calibrate.add_argument("--feedback", type=Path, required=True, help="Calibration feedback TOML file.")
    p_baseline_calibrate.add_argument("--predictions", type=Path, help="Prediction JSON sidecar to calibrate.")
    p_baseline_calibrate.add_argument("--output", type=Path, help="Calibration summary Markdown output path.")
    p_baseline_calibrate.add_argument("--dry-run", action="store_true")
    p_baseline_calibrate.set_defaults(func=_handle_baseline_calibrate)

    p_baseline_promote = baseline_sub.add_parser(
        "promote",
        help="Promote accepted guardrail predictions into baseline/global files.",
    )
    p_baseline_promote.add_argument("--feedback", type=Path, required=True, help="Calibration feedback TOML file.")
    p_baseline_promote.add_argument("--predictions", type=Path, help="Prediction JSON sidecar to promote from.")
    p_baseline_promote.add_argument("--id", action="append", dest="promote_ids", help="Promote only this prediction id.")
    p_baseline_promote.add_argument("--dry-run", action="store_true")
    p_baseline_promote.set_defaults(func=_handle_baseline_promote)

    p_baseline_publish = baseline_sub.add_parser(
        "publish",
        help="Generate agent-specific baseline slices from promoted global files.",
    )
    p_baseline_publish.add_argument(
        "--agent",
        action="append",
        dest="publish_agents",
        choices=("codex", "claude", "vscode"),
        help="Publish only selected agent targets. Default: all.",
    )
    p_baseline_publish.add_argument("--dry-run", action="store_true")
    p_baseline_publish.set_defaults(func=_handle_baseline_publish)

    p_baseline_eval = baseline_sub.add_parser("eval", help="Evaluate baseline loop efficacy gates E1-E6.")
    p_baseline_eval.add_argument("--output", type=Path, help="Evaluation report Markdown output path.")
    p_baseline_eval.add_argument("--dry-run", action="store_true")
    p_baseline_eval.set_defaults(func=_handle_baseline_eval)

    p_baseline_lint = baseline_sub.add_parser("lint", help="Lint baseline schema, marker blocks, links, and pages.")
    p_baseline_lint.add_argument("--output", type=Path, help="Optional lint report Markdown output path.")
    p_baseline_lint.add_argument("--stale-days", type=int, default=90, help="Generated block age warning threshold.")
    p_baseline_lint.add_argument("--dry-run", action="store_true")
    p_baseline_lint.set_defaults(func=_handle_baseline_lint)

    p_baseline_ingest = baseline_sub.add_parser(
        "ingest",
        help="Ingest structured JSON proposals from baseline/proposals/.",
    )
    p_baseline_ingest.add_argument("--proposal", type=Path, help="Single proposal JSON file to ingest.")
    p_baseline_ingest.add_argument("--output", type=Path, help="Optional ingest report output path.")
    p_baseline_ingest.add_argument("--dry-run", action="store_true")
    p_baseline_ingest.set_defaults(func=_handle_baseline_ingest)

    p_baseline_bundle = baseline_sub.add_parser("bundle", help="Create a bounded evidence bundle for an AI agent.")
    p_baseline_bundle.add_argument("--output-dir", type=Path, help="Bundle output directory.")
    p_baseline_bundle.add_argument("--max-sessions", type=int, default=12)
    p_baseline_bundle.add_argument("--max-chars-per-session", type=int, default=2500)
    p_baseline_bundle.add_argument(
        "--access-level",
        choices=(
            "session-only",
            "repo-read-only",
            "collaboration-metadata",
            "local-agent-context",
            "write-candidates",
        ),
        default="session-only",
    )
    p_baseline_bundle.add_argument("--focus", action="append", help="Focus keyword or project slug. Can be repeated.")
    p_baseline_bundle.add_argument("--dry-run", action="store_true")
    p_baseline_bundle.set_defaults(func=_handle_baseline_bundle)

    p_baseline_handoffs = baseline_sub.add_parser("handoffs", help="Audit or index session handoff artifacts.")
    handoffs_sub = p_baseline_handoffs.add_subparsers(dest="handoffs_cmd", required=True)
    p_handoffs_audit = handoffs_sub.add_parser(
        "audit",
        help="Write a report-only handoff coverage and freshness audit.",
    )
    p_handoffs_audit.add_argument("--output", type=Path, help="Audit Markdown output path.")
    p_handoffs_audit.add_argument("--stale-days", type=int, default=90, help="Freshness threshold in days.")
    p_handoffs_audit.add_argument(
        "--max-archive-records",
        type=int,
        default=0,
        help="Maximum archive records to scan; 0 scans all indexed records.",
    )
    p_handoffs_audit.add_argument("--dry-run", action="store_true")
    p_handoffs_audit.set_defaults(func=_handle_baseline_handoffs_audit)

    p_handoffs_index = handoffs_sub.add_parser(
        "index",
        help="Write persistent handoff index records and project-page feeds.",
    )
    p_handoffs_index.add_argument("--output", type=Path, help="Handoff JSONL index output path.")
    p_handoffs_index.add_argument(
        "--max-archive-records",
        type=int,
        default=0,
        help="Maximum archive records to scan; 0 scans all indexed records.",
    )
    p_handoffs_index.add_argument("--dry-run", action="store_true")
    p_handoffs_index.set_defaults(func=_handle_baseline_handoffs_index)

    p_handoffs_proposals = handoffs_sub.add_parser(
        "proposals",
        help="Write handoff-derived proposal JSON with structured trace records.",
    )
    p_handoffs_proposals.add_argument("--index", type=Path, help="Handoff JSONL index path.")
    p_handoffs_proposals.add_argument("--output-dir", type=Path, help="Proposal JSON output directory.")
    p_handoffs_proposals.add_argument(
        "--max-records-per-project",
        type=int,
        default=5,
        help="Maximum handoff records to cite per generated project proposal.",
    )
    p_handoffs_proposals.add_argument("--dry-run", action="store_true")
    p_handoffs_proposals.set_defaults(func=_handle_baseline_handoffs_proposals)

    p_baseline_replay = baseline_sub.add_parser("replay", help="Select, bundle, and ingest cross-agent replay work.")
    replay_sub = p_baseline_replay.add_subparsers(dest="replay_cmd", required=True)
    p_replay_select = replay_sub.add_parser(
        "select",
        help="Write a deterministic replay-candidate manifest (no excerpts), excluding coding sessions.",
    )
    p_replay_select.add_argument("--kind", help="Only select sessions whose inferred kind matches (e.g. planning).")
    p_replay_select.add_argument("--limit", type=int, default=20, help="Maximum sessions to select.")
    p_replay_select.add_argument("--output", type=Path, help="Manifest JSONL output path.")
    p_replay_select.add_argument(
        "--max-archive-records",
        type=int,
        default=0,
        help="Maximum archive records to scan; 0 scans all indexed records.",
    )
    p_replay_select.add_argument("--dry-run", action="store_true")
    p_replay_select.set_defaults(func=_handle_baseline_replay_select)

    p_replay_redact = replay_sub.add_parser(
        "redact",
        help="Fail-closed redaction preflight over selected replay sessions (blocks on high-confidence secrets).",
    )
    p_replay_redact.add_argument("--manifest", type=Path, help="Replay manifest JSONL path.")
    p_replay_redact.add_argument("--output", type=Path, help="Redaction report JSON output path (gitignored by default).")
    p_replay_redact.add_argument("--limit", type=int, default=0, help="Maximum selected sessions to scan; 0 scans all.")
    p_replay_redact.add_argument("--dry-run", action="store_true")
    p_replay_redact.set_defaults(func=_handle_baseline_replay_redact)

    p_replay_bundle = replay_sub.add_parser(
        "bundle",
        help="Write gitignored replay packets (redacted task + deliverable + rubric) for selected sessions.",
    )
    p_replay_bundle.add_argument("--manifest", type=Path, help="Replay manifest JSONL path.")
    p_replay_bundle.add_argument("--output-dir", type=Path, help="Bundle output directory (gitignored by default).")
    p_replay_bundle.add_argument("--limit", type=int, default=0, help="Maximum selected sessions to bundle; 0 = all.")
    p_replay_bundle.add_argument(
        "--access-tier",
        default="session-only",
        help="Access tier recorded in each packet's constraint block.",
    )
    p_replay_bundle.add_argument("--dry-run", action="store_true")
    p_replay_bundle.set_defaults(func=_handle_baseline_replay_bundle)

    p_replay_ingest = replay_sub.add_parser(
        "ingest",
        help="Validate an external replay result into replay.* proposals and the append-only replay ledger.",
    )
    p_replay_ingest.add_argument("--result", type=Path, help="Replay result JSON path (one object or a list).")
    p_replay_ingest.add_argument("--output-dir", type=Path, help="Proposal JSON output directory.")
    p_replay_ingest.add_argument("--ledger", type=Path, help="Replay ledger JSONL path.")
    p_replay_ingest.add_argument("--dry-run", action="store_true")
    p_replay_ingest.set_defaults(func=_handle_baseline_replay_ingest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.repo_root.resolve(), args.config)
    return int(args.func(config, args))
