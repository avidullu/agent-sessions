"""Command-line interface for the archive tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from .archive import discover_sources, export_sources, pdf_existing
from .baseline import baseline_scaffold, baseline_suggest
from .config import load_config


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export local coding-agent sessions.")
    parser.add_argument("--config", type=Path, help="Optional sources TOML path.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_discover = sub.add_parser("discover", help="Discover configured local stores.")
    p_discover.add_argument("--samples", type=int, default=10)
    p_discover.add_argument("--write", help="Write Markdown discovery report to this path.")

    p_export = sub.add_parser("export", help="Export configured local stores.")
    p_export.add_argument("--all", action="store_true", help="Export all configured sources.")
    p_export.add_argument("--source", action="append", help="Source name or kind to export. Can be repeated.")
    p_export.add_argument("--limit", type=int, help="Maximum files to export, useful for tests.")
    p_export.add_argument("--pdf", action="store_true", help="Also write simple PDFs when reportlab is installed.")
    p_export.add_argument("--copy-raw", action="store_true", help="Copy gzip-compressed raw source files to raw/.")
    p_export.add_argument("--dry-run", action="store_true")

    p_pdf = sub.add_parser("pdf", help="Generate PDFs from existing archive Markdown.")
    p_pdf.add_argument("--all", action="store_true", help="Generate PDFs for all indexed Markdown files.")
    p_pdf.add_argument("--source", action="append", help="Source name or kind to PDF. Can be repeated.")
    p_pdf.add_argument("--limit", type=int, help="Maximum PDFs to write.")
    p_pdf.add_argument("--force", action="store_true", help="Overwrite existing PDFs.")

    p_baseline = sub.add_parser("baseline", help="Work with engineering baseline candidates.")
    baseline_sub = p_baseline.add_subparsers(dest="baseline_cmd", required=True)

    p_baseline_scaffold = baseline_sub.add_parser("scaffold", help="Create missing baseline folders/templates.")
    p_baseline_scaffold.add_argument("--dry-run", action="store_true")

    p_baseline_suggest = baseline_sub.add_parser("suggest", help="Generate reviewable baseline candidate suggestions.")
    p_baseline_suggest.add_argument("--output", type=Path, help="Candidate Markdown output path.")
    p_baseline_suggest.add_argument(
        "--max-sessions",
        type=int,
        default=500,
        help="Maximum Markdown sessions to scan for text signals. Use 0 for all indexed sessions.",
    )
    p_baseline_suggest.add_argument("--feedback", type=Path, help="Optional calibration feedback TOML file.")
    p_baseline_suggest.add_argument("--dry-run", action="store_true")

    p_baseline_calibrate = baseline_sub.add_parser("calibrate", help="Summarize calibration feedback for predictions.")
    p_baseline_calibrate.add_argument("--feedback", type=Path, required=True, help="Calibration feedback TOML file.")
    p_baseline_calibrate.add_argument("--predictions", type=Path, help="Prediction JSON sidecar to calibrate.")
    p_baseline_calibrate.add_argument("--output", type=Path, help="Calibration summary Markdown output path.")
    p_baseline_calibrate.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(REPO_ROOT, args.config)

    if args.cmd == "discover":
        return discover_sources(config, samples=args.samples, write=args.write)
    if args.cmd == "export":
        if not args.all and not args.source:
            parser.error("export requires --all or at least one --source")
        result = export_sources(
            config,
            selected=args.source,
            limit=args.limit,
            write_pdfs=args.pdf,
            copy_raw_files=args.copy_raw,
            dry_run=args.dry_run,
        )
        print(f"Exported {result.exported} session files.")
        if result.skipped_sources:
            print("Skipped sources without extractors:")
            for source in result.skipped_sources:
                print(f"- {source}")
        if result.pdf_missing:
            print("PDF export requested but reportlab is not installed. Run: python -m pip install reportlab")
        return 0
    if args.cmd == "pdf":
        if not args.all and not args.source:
            parser.error("pdf requires --all or at least one --source")
        return pdf_existing(config, selected=args.source, limit=args.limit, force=args.force)
    if args.cmd == "baseline":
        if args.baseline_cmd == "scaffold":
            return baseline_scaffold(config, dry_run=args.dry_run)
        if args.baseline_cmd == "suggest":
            return baseline_suggest(
                config,
                output=args.output,
                max_sessions=args.max_sessions,
                feedback=args.feedback,
                dry_run=args.dry_run,
            )
        if args.baseline_cmd == "calibrate":
            from .baseline import baseline_calibrate

            return baseline_calibrate(
                config,
                feedback=args.feedback,
                predictions=args.predictions,
                output=args.output,
                dry_run=args.dry_run,
            )
    parser.error(f"Unknown command: {args.cmd}")
    return 2
