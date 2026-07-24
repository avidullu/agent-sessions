"""Tests for tools/check_md_links.py — the internal-markdown-link CI guard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import check_md_links as C


def _check(tmp_path: Path, files: dict[str, str]) -> list[tuple[str, int, str]]:
    """Write {relpath: body} under tmp_path, then run check_file on each .md (no git needed)."""
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    cache: dict[str, Any] = {}
    out: list[tuple[str, int, str]] = []
    for rel in files:
        if rel.endswith(".md"):
            out += [(rel, ln, r) for ln, r in C.check_file(tmp_path, rel, cache)]
    return out


# --------------------------------------------------------------------- slug / heading parsing
def test_slugify_matches_github_double_hyphen_on_removed_punct() -> None:
    # '/' is dropped but its surrounding spaces each become a hyphen (NO collapsing) -> '--'.
    assert C.slugify("Q5: Why A / B?") == "q5-why-a--b"
    assert C.slugify("4. Open decisions (for the owner)") == "4-open-decisions-for-the-owner"


def test_heading_slugs_dedup_and_skips_fences() -> None:
    s = C.heading_slugs("# Foo\n## Foo\n```\n# Not A Heading\n```\n")
    assert "foo" in s and "foo-1" in s and "not-a-heading" not in s


# --------------------------------------------------------------------- link checking
def test_valid_link_and_anchor_pass(tmp_path: Path) -> None:
    files = {
        "a.md": "See [b](b.md#sec-two) and [self](#top).\n# Top\n",
        "b.md": "# Intro\n## Sec Two\n",
    }
    assert _check(tmp_path, files) == []


def test_missing_file_flagged(tmp_path: Path) -> None:
    f = _check(tmp_path, {"a.md": "[x](nope.md)\n"})
    assert len(f) == 1 and "broken link" in f[0][2]


def test_dead_anchor_flagged(tmp_path: Path) -> None:
    f = _check(tmp_path, {"a.md": "[x](#no-such)\n# Real\n"})
    assert len(f) == 1 and "broken anchor" in f[0][2]


def test_external_and_fenced_are_skipped(tmp_path: Path) -> None:
    body = "[h](https://x.com/y) [m](mailto:a@b.c)\n```\n[code](nope.md)\n```\n"
    assert _check(tmp_path, {"a.md": body}) == []


def test_link_to_existing_archived_file_is_ok(tmp_path: Path) -> None:
    files = {"live.md": "[a](archives/old.md)\n", "archives/old.md": "# Old\n"}
    assert _check(tmp_path, files) == []


def test_title_suffix_is_stripped(tmp_path: Path) -> None:
    files = {"a.md": '[x](b.md "a title")\n', "b.md": "# B\n"}
    assert _check(tmp_path, files) == []
