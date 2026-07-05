"""Markdown and PDF rendering."""

from __future__ import annotations

import datetime as dt
import re
import textwrap
from pathlib import Path

from .models import ExtractedSession, Source
from .utils import now_utc


def markdown_for_session(source: Source, path: Path, session: ExtractedSession, digest: str) -> str:
    title_bits = [source.name, str(session.metadata.get("session_id") or path.stem)]
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
        f"- Source modified: `{modified_timestamp(path)}`",
        f"- Imported at: `{now_utc()}`",
    ]
    for key in sorted(session.metadata):
        value = session.metadata[key]
        if value in (None, ""):
            continue
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Transcript", ""])
    if not session.messages:
        lines.append("_No transcript messages were extracted from this file._")
        return "\n".join(lines) + "\n"
    for idx, msg in enumerate(session.messages, 1):
        heading = f"### {idx}. {msg.role or 'message'}"
        if msg.timestamp:
            heading += f" ({msg.timestamp})"
        lines.extend([heading, "", msg.text.rstrip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def modified_timestamp(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat(timespec="seconds")


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
