#!/usr/bin/env python3
"""Export local coding-agent sessions to Markdown and optional PDFs."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = REPO_ROOT / "archive"
RAW_DIR = REPO_ROOT / "raw"


@dataclass(frozen=True)
class Source:
    name: str
    kind: str
    roots: tuple[Path, ...]
    glob: str


DEFAULT_SOURCES = [
    {
        "name": "codex-windows",
        "kind": "codex",
        "roots": [
            r"%USERPROFILE%\.codex\sessions",
            r"%USERPROFILE%\.codex\archived_sessions",
        ],
        "glob": "**/*.jsonl",
    },
    {
        "name": "claude-windows",
        "kind": "claude",
        "roots": [r"%USERPROFILE%\.claude\projects"],
        "glob": "**/*.jsonl",
    },
    {
        "name": "claude-wsl-ubuntu",
        "kind": "claude",
        "roots": [r"\\wsl.localhost\Ubuntu\home\avidullu\.claude\projects"],
        "glob": "**/*.jsonl",
    },
    {
        "name": "gemini-antigravity-windows",
        "kind": "gemini_antigravity",
        "roots": [r"%USERPROFILE%\.gemini\antigravity\brain"],
        "glob": "**/transcript*.jsonl",
    },
    {
        "name": "grok-wsl-ubuntu",
        "kind": "grok",
        "roots": [r"\\wsl.localhost\Ubuntu\home\avidullu\.grok\sessions"],
        "glob": "**/chat_history.jsonl",
    },
    {
        "name": "deepseek-vscode-windows",
        "kind": "deepseek_request_dump",
        "roots": [
            r"%APPDATA%\Code\User\globalStorage\vizards.deepseek-v4-for-copilot\request-dumps",
        ],
        "glob": "**/*.msg*.txt",
    },
    {
        "name": "deepseek-vscode-wsl-ubuntu",
        "kind": "deepseek_request_dump",
        "roots": [
            r"\\wsl.localhost\Ubuntu\home\avidullu\.vscode-server\data\User\globalStorage\vizards.deepseek-v4-for-copilot\request-dumps",
        ],
        "glob": "**/*.msg*.txt",
    },
    {
        "name": "copilot-vscode-windows-inventory",
        "kind": "inventory",
        "roots": [r"%APPDATA%\Code\User\globalStorage\github.copilot-chat"],
        "glob": "**/*",
    },
    {
        "name": "copilot-vscode-wsl-ubuntu-inventory",
        "kind": "inventory",
        "roots": [
            r"\\wsl.localhost\Ubuntu\home\avidullu\.vscode-server\data\User\globalStorage\github.copilot-chat",
        ],
        "glob": "**/*",
    },
    {
        "name": "zai-vscode-wsl-ubuntu-inventory",
        "kind": "inventory",
        "roots": [
            r"\\wsl.localhost\Ubuntu\home\avidullu\.vscode-server\extensions\ltmoerdani.zai-copilot-chat-0.3.1",
        ],
        "glob": "**/*",
    },
]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(raw)).expanduser()


def load_sources(config: Path | None) -> list[Source]:
    config_path = config or (REPO_ROOT / "sources.toml")
    data: dict[str, Any]
    if config_path.exists():
        if tomllib is None:
            raise SystemExit("Python 3.11+ is required to read TOML config.")
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        items = data.get("sources", [])
    else:
        items = DEFAULT_SOURCES
    sources: list[Source] = []
    for item in items:
        sources.append(
            Source(
                name=item["name"],
                kind=item["kind"],
                roots=tuple(expand_path(p) for p in item.get("roots", [])),
                glob=item.get("glob", "**/*"),
            )
        )
    return sources


def iter_source_files(source: Source) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in source.roots:
        if not root.exists():
            continue
        for path in root.glob(source.glob):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^\w.\- ]+", "-", value, flags=re.ASCII)
    value = re.sub(r"\s+", "-", value.strip())
    value = value.strip(".-_")
    return (value[:max_len].strip(".-_") or "session").lower()


def jsonl_objects(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def text_from_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(text_from_content(item.get("text")))
                elif "content" in item:
                    parts.append(text_from_content(item.get("content")))
                elif "input" in item:
                    parts.append(text_from_content(item.get("input")))
        return "\n".join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ("text", "content", "message", "input", "output"):
            if key in value:
                return text_from_content(value[key])
    return ""


def extract_codex(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    metadata: dict[str, Any] = {"session_id": session_id_from_name(path)}
    messages: list[dict[str, str]] = []
    for obj in jsonl_objects(path):
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        if obj.get("type") == "session_meta":
            metadata.update(
                {
                    "session_id": payload.get("session_id") or payload.get("id") or metadata["session_id"],
                    "cwd": payload.get("cwd"),
                    "model_provider": payload.get("model_provider"),
                    "cli_version": payload.get("cli_version"),
                    "source": payload.get("source"),
                }
            )
            continue
        role = payload.get("role")
        content = text_from_content(payload.get("content"))
        if role and content:
            messages.append({"role": role, "text": content, "timestamp": obj.get("timestamp", "")})
    return metadata, messages


def extract_claude(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    metadata: dict[str, Any] = {"session_id": path.stem, "project": path.parent.name}
    messages: list[dict[str, str]] = []
    for obj in jsonl_objects(path):
        if obj.get("sessionId"):
            metadata["session_id"] = obj.get("sessionId")
        message = obj.get("message")
        if isinstance(message, dict):
            role = message.get("role") or obj.get("type") or "message"
            content = text_from_content(message.get("content"))
            if content:
                messages.append({"role": role, "text": content, "timestamp": obj.get("timestamp", "")})
            continue
        if obj.get("type") == "summary" and obj.get("content"):
            messages.append(
                {"role": "summary", "text": text_from_content(obj.get("content")), "timestamp": obj.get("timestamp", "")}
            )
    return metadata, messages


def extract_gemini(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    metadata: dict[str, Any] = {"session_id": path.parents[2].name if len(path.parents) > 2 else path.stem}
    messages: list[dict[str, str]] = []
    for obj in jsonl_objects(path):
        content = text_from_content(obj.get("content"))
        if not content:
            continue
        role = obj.get("source") or obj.get("type") or "message"
        timestamp = obj.get("created_at") or obj.get("timestamp") or ""
        messages.append({"role": role, "text": content, "timestamp": timestamp})
    return metadata, messages


def extract_grok(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    session_id = path.parent.name
    project = path.parent.parent.name
    metadata: dict[str, Any] = {"session_id": session_id, "project": project}
    messages: list[dict[str, str]] = []
    for obj in jsonl_objects(path):
        content = text_from_content(obj.get("content"))
        if not content:
            continue
        role = obj.get("type") or "message"
        messages.append({"role": role, "text": content, "timestamp": obj.get("timestamp", "")})
    return metadata, messages


def extract_deepseek_prompt(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    metadata = {"session_id": path.parent.name, "request_file": path.name}
    text = path.read_text(encoding="utf-8", errors="replace")
    messages = [{"role": "request-prompt", "text": text, "timestamp": ""}] if text.strip() else []
    return metadata, messages


EXTRACTORS = {
    "codex": extract_codex,
    "claude": extract_claude,
    "gemini_antigravity": extract_gemini,
    "grok": extract_grok,
    "deepseek_request_dump": extract_deepseek_prompt,
}


def session_id_from_name(path: Path) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path.name, re.I)
    return match.group(1) if match else path.stem


def markdown_for_session(
    source: Source,
    path: Path,
    metadata: dict[str, Any],
    messages: list[dict[str, str]],
    digest: str,
) -> str:
    title_bits = [source.name, str(metadata.get("session_id") or path.stem)]
    title = " / ".join(x for x in title_bits if x)
    lines = [
        f"# {title}",
        "",
        "## Metadata",
        "",
        f"- Source: `{source.name}`",
        f"- Kind: `{source.kind}`",
        f"- Source file: `{path}`",
        f"- SHA-256: `{digest}`",
        f"- Source modified: `{dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat(timespec='seconds')}`",
        f"- Imported at: `{now_utc()}`",
    ]
    for key in sorted(metadata):
        value = metadata[key]
        if value in (None, ""):
            continue
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Transcript", ""])
    if not messages:
        lines.append("_No transcript messages were extracted from this file._")
        return "\n".join(lines) + "\n"
    for idx, msg in enumerate(messages, 1):
        role = msg.get("role") or "message"
        timestamp = msg.get("timestamp") or ""
        heading = f"### {idx}. {role}"
        if timestamp:
            heading += f" ({timestamp})"
        lines.extend([heading, "", msg.get("text", "").rstrip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def write_pdf(markdown: str, out_path: Path) -> bool:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        return False

    ansi = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    pdf = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter
    margin = 42
    y = height - margin
    line_height = 11
    max_chars = 96

    def emit(line: str, font: str = "Courier", size: int = 8) -> None:
        nonlocal y
        if y < margin:
            pdf.showPage()
            y = height - margin
        pdf.setFont(font, size)
        safe = ansi.sub("", line).encode("latin-1", "replace").decode("latin-1")
        pdf.drawString(margin, y, safe)
        y -= line_height

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            y -= 4
            emit(line[2:], "Helvetica-Bold", 14)
            y -= 4
            continue
        if line.startswith("## "):
            y -= 3
            emit(line[3:], "Helvetica-Bold", 11)
            y -= 2
            continue
        if line.startswith("### "):
            y -= 2
            emit(line[4:], "Helvetica-Bold", 9)
            continue
        if not line:
            y -= line_height
            continue
        for wrapped in textwrap.wrap(line, width=max_chars, replace_whitespace=False) or [""]:
            emit(wrapped)
    pdf.save()
    return True


def copy_raw(path: Path, source: Source, digest: str) -> Path:
    raw_target = RAW_DIR / source.name / f"{digest[:16]}-{path.name}.gz"
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    with path.open("rb") as src, gzip.open(raw_target, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return raw_target


def export_sources(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    selected = set(args.source or [])
    if selected:
        sources = [s for s in sources if s.name in selected or s.kind in selected]
    ARCHIVE_DIR.mkdir(exist_ok=True)
    records: list[dict[str, Any]] = []
    pdf_missing = False
    exported = 0
    for source in sources:
        extractor = EXTRACTORS.get(source.kind)
        if extractor is None:
            continue
        for path in iter_source_files(source):
            if args.limit and exported >= args.limit:
                break
            digest = sha256_file(path)
            metadata, messages = extractor(path)
            session_id = str(metadata.get("session_id") or path.stem)
            changed = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d")
            stem = slugify(f"{changed}-{session_id}-{path.stem}-{digest[:12]}")
            out_dir = ARCHIVE_DIR / source.name
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / f"{stem}.md"
            markdown = markdown_for_session(source, path, metadata, messages, digest)
            if not args.dry_run:
                md_path.write_text(markdown, encoding="utf-8", newline="\n")
            pdf_path = None
            if args.pdf:
                pdf_path = md_path.with_suffix(".pdf")
                if not args.dry_run and not write_pdf(markdown, pdf_path):
                    pdf_missing = True
                    pdf_path = None
            raw_path = None
            if args.copy_raw and not args.dry_run:
                raw_path = copy_raw(path, source, digest)
            records.append(
                {
                    "source": source.name,
                    "kind": source.kind,
                    "source_file": str(path),
                    "sha256": digest,
                    "messages": len(messages),
                    "markdown": str(md_path.relative_to(REPO_ROOT)),
                    "pdf": str(pdf_path.relative_to(REPO_ROOT)) if pdf_path else None,
                    "raw": str(raw_path.relative_to(REPO_ROOT)) if raw_path else None,
                    "metadata": metadata,
                }
            )
            exported += 1
        if args.limit and exported >= args.limit:
            break
    if not args.dry_run:
        write_indexes(records)
    print(f"Exported {exported} session files.")
    if pdf_missing:
        print("PDF export requested but reportlab is not installed. Run: python -m pip install reportlab")
    return 0


def write_indexes(records: list[dict[str, Any]]) -> None:
    jsonl_path = ARCHIVE_DIR / "index.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    lines = [
        "# Agent Session Archive",
        "",
        f"Generated: `{now_utc()}`",
        "",
        "| Source | Kind | Messages | Markdown | PDF |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for record in records:
        md = record["markdown"].replace("\\", "/")
        link = os.path.relpath(REPO_ROOT / md, ARCHIVE_DIR).replace("\\", "/")
        pdf = record.get("pdf")
        pdf_link = ""
        if pdf:
            pdf_norm = pdf.replace("\\", "/")
            pdf_rel = os.path.relpath(REPO_ROOT / pdf_norm, ARCHIVE_DIR).replace("\\", "/")
            pdf_link = f"[PDF]({pdf_rel})"
        lines.append(
            f"| {record['source']} | {record['kind']} | {record['messages']} | "
            f"[{Path(md).name}]({link}) | {pdf_link} |"
        )
    (ARCHIVE_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def load_index_records() -> list[dict[str, Any]]:
    index_path = ARCHIVE_DIR / "index.jsonl"
    if not index_path.exists():
        raise SystemExit("archive/index.jsonl does not exist. Run export first.")
    records: list[dict[str, Any]] = []
    with index_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def pdf_existing(args: argparse.Namespace) -> int:
    records = load_index_records()
    selected = set(args.source or [])
    made = 0
    skipped = 0
    missing_renderer = False
    for record in records:
        if selected and record.get("source") not in selected and record.get("kind") not in selected:
            continue
        if args.limit and made >= args.limit:
            break
        md_path = REPO_ROOT / record["markdown"]
        if not md_path.exists():
            skipped += 1
            continue
        pdf_path = md_path.with_suffix(".pdf")
        if pdf_path.exists() and not args.force:
            record["pdf"] = str(pdf_path.relative_to(REPO_ROOT))
            skipped += 1
            continue
        markdown = md_path.read_text(encoding="utf-8", errors="replace")
        ok = write_pdf(markdown, pdf_path)
        if not ok:
            missing_renderer = True
            break
        record["pdf"] = str(pdf_path.relative_to(REPO_ROOT))
        made += 1
    write_indexes(records)
    print(f"PDFs written: {made}; skipped: {skipped}.")
    if missing_renderer:
        print("PDF export requires reportlab. Run: python -m pip install reportlab")
        return 1
    return 0
    (ARCHIVE_DIR / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def discover_sources(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    lines = ["# Agent Session Discovery", "", f"Generated: `{now_utc()}`", ""]
    for source in sources:
        lines.extend([f"## {source.name}", "", f"- Kind: `{source.kind}`", f"- Glob: `{source.glob}`"])
        total_files = 0
        total_bytes = 0
        found_roots: list[str] = []
        for root in source.roots:
            exists = root.exists()
            lines.append(f"- Root: `{root}` ({'exists' if exists else 'missing'})")
            if not exists:
                continue
            found_roots.append(str(root))
            files = list(root.glob(source.glob))
            files = [p for p in files if p.is_file()]
            total_files += len(files)
            total_bytes += sum(p.stat().st_size for p in files)
        lines.extend([f"- Matching files: `{total_files}`", f"- Matching bytes: `{total_bytes}`", ""])
        sample_count = 0
        for path in iter_source_files(source):
            lines.append(f"  - `{path}` ({path.stat().st_size} bytes)")
            sample_count += 1
            if sample_count >= args.samples:
                break
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    if args.write:
        target = Path(args.write)
        if not target.is_absolute():
            target = REPO_ROOT / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Optional sources TOML path.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_discover = sub.add_parser("discover", help="Discover configured local stores.")
    p_discover.add_argument("--samples", type=int, default=10)
    p_discover.add_argument("--write", help="Write Markdown discovery report to this path.")
    p_discover.set_defaults(func=discover_sources)

    p_export = sub.add_parser("export", help="Export configured local stores.")
    p_export.add_argument("--all", action="store_true", help="Export all configured sources.")
    p_export.add_argument("--source", action="append", help="Source name or kind to export. Can be repeated.")
    p_export.add_argument("--limit", type=int, help="Maximum files to export, useful for tests.")
    p_export.add_argument("--pdf", action="store_true", help="Also write simple PDFs when reportlab is installed.")
    p_export.add_argument("--copy-raw", action="store_true", help="Copy gzip-compressed raw source files to raw/.")
    p_export.add_argument("--dry-run", action="store_true")
    p_export.set_defaults(func=export_sources)

    p_pdf = sub.add_parser("pdf", help="Generate PDFs from existing archive Markdown.")
    p_pdf.add_argument("--all", action="store_true", help="Generate PDFs for all indexed Markdown files.")
    p_pdf.add_argument("--source", action="append", help="Source name or kind to PDF. Can be repeated.")
    p_pdf.add_argument("--limit", type=int, help="Maximum PDFs to write.")
    p_pdf.add_argument("--force", action="store_true", help="Overwrite existing PDFs.")
    p_pdf.set_defaults(func=pdf_existing)

    args = parser.parse_args(argv)
    if args.cmd == "export" and not args.all and not args.source:
        parser.error("export requires --all or at least one --source")
    if args.cmd == "pdf" and not args.all and not args.source:
        parser.error("pdf requires --all or at least one --source")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
