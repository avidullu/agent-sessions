"""Markdown internal-link checker — fail CI on a broken internal link in a LIVE doc.

Scans tracked ``*.md`` files (via ``git ls-files``) and, for each ``[text](dest)`` / ``![alt](dest)``
link whose destination is INTERNAL (a repo path and/or a ``#anchor``), verifies that

  - the target file exists (resolved relative to the linking file, or the repo root for ``/abs``), and
  - any ``#anchor`` matches a GitHub-style heading slug in the target markdown file.

SKIPPED: external links (``http(s)``/``mailto``/``tel``/``ftp``/protocol-relative ``//``), links inside
fenced code blocks, and any file under ``docs/archives/**`` — archived docs are frozen snapshots whose
relative links are historical-by-design (see ``docs/DOC_STATUS.md`` §2). Mirrors ``tools/leak_scan.py``:
run ``python -m tools.check_md_links`` (exit 1 on any broken internal link in a live doc).

Borrowed from ``badminton-highlight-indexer`` (Khelsutra) — same implementation, adapted for
``agent-sessions`` path conventions.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

#: Source docs under these prefixes are NOT scanned — archived = frozen snapshots whose relative
#: links are historical-by-design (DOC_STATUS.md §2 step 5). baseline/projects/ READMEs are
#: generated catalog artifacts that link to local-only transcript files — not live docs.
EXCLUDE_PREFIXES: tuple[str, ...] = ("docs/archives/", "baseline/projects/")
#: This tool + its test legitimately embed sample/broken links — never scan them.
SELF_EXCLUDE: tuple[str, ...] = ("tools/check_md_links.py", "tests/test_check_md_links.py")

_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)]+?)\s*\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
#: a scheme (``http:``, ``mailto:``, …) or protocol-relative ``//`` ⇒ external, not our concern.
_EXTERNAL_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//)")


def slugify(heading: str) -> str:
    """GitHub-style heading → anchor slug (matches ``github-slugger``): lowercase, drop punctuation
    (keep word chars / spaces / hyphens), then replace EACH space with a hyphen — crucially NOT
    collapsing, so a heading with removed punctuation (e.g. 'a / b' → 'a  b') yields '--' like GitHub."""
    s = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return s.replace(" ", "-")


def heading_slugs(text: str) -> set[str]:
    """The set of GitHub anchor slugs for a markdown file's headings (with -1/-2 dedup suffixes)."""
    counts: dict[str, int] = {}
    out: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        base = slugify(m.group(2))
        n = counts.get(base, 0)
        out.add(base if n == 0 else f"{base}-{n}")
        counts[base] = n + 1
    return out


def _split_dest(dest: str) -> tuple[str, str]:
    """``path#anchor`` (with an optional ``\"title\"`` suffix) → ``(path, anchor)``."""
    dest = dest.strip().split()[0]  # drop a trailing "title"
    path, _, anchor = dest.partition("#")
    return path, anchor


def check_file(repo: Path, rel: str, slug_cache: dict[str, set[str]]) -> list[tuple[int, str]]:
    md = repo / rel
    base = md.parent
    findings: list[tuple[int, str]] = []
    in_fence = False
    for i, line in enumerate(md.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in _LINK_RE.finditer(line):
            dest = m.group(1).strip()
            if not dest or _EXTERNAL_RE.match(dest):
                continue
            path, anchor = _split_dest(dest)
            if path == "":
                target = md  # pure same-file anchor
            elif path.startswith("/"):
                target = repo / path.lstrip("/")
            else:
                target = (base / path).resolve()
            if path != "" and not target.exists():
                findings.append((i, f"broken link -> {dest} (no file {path})"))
                continue
            if anchor and target.suffix.lower() == ".md" and target.is_file():
                key = str(target)
                if key not in slug_cache:
                    slug_cache[key] = heading_slugs(
                        target.read_text(encoding="utf-8", errors="replace")
                    )
                if slugify(anchor) not in slug_cache[key]:
                    findings.append((i, f"broken anchor -> {dest} (no heading #{anchor})"))
    return findings


def tracked_md(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=str(repo), capture_output=True, text=True
    )
    files = sorted({f.strip() for f in out.stdout.splitlines() if f.strip()})
    return [
        f for f in files if not f.startswith(EXCLUDE_PREFIXES) and f not in SELF_EXCLUDE
    ]


def scan_repo(repo: Path) -> list[tuple[str, int, str]]:
    slug_cache: dict[str, set[str]] = {}
    results: list[tuple[str, int, str]] = []
    for rel in tracked_md(repo):
        try:
            for lineno, reason in check_file(repo, rel, slug_cache):
                results.append((rel, lineno, reason))
        except OSError:
            continue
    return results


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check internal markdown links in LIVE docs (excludes docs/archives/)."
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: the parent of tools/)",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)
    results = scan_repo(args.root)
    if not results:
        print("[check-md-links] clean — no broken internal links in live docs.")
        return 0
    print(f"[check-md-links] {len(results)} broken internal link(s):", file=sys.stderr)
    for rel, lineno, reason in results:
        print(f"  {rel}:{lineno}: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
