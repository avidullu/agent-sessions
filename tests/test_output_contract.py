"""Output-contract conformance for the hub side of ``docs/OUTPUT_CONTRACT.md``.

``render.py`` (and the archive naming logic) must reproduce the frozen golden
Markdown, filename stem, and index record for every fixture under
``tests/fixtures/contract/v1/``. Feeder tools (e.g. the agent-session-router
VS Code extension) vendor these same fixtures and assert their own renderer
produces identical bytes, so the two implementations cannot drift apart.

Regenerate goldens after an intentional format change with::

    AGENT_SESSIONS_UPDATE_GOLDENS=1 python -m pytest tests/test_output_contract.py

The ``__SOURCE_FILE__`` placeholder stands in for the (environment-specific)
native source path, which the contract deliberately leaves un-normalized.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

import pytest

from agent_sessions.archive import dt_from_timestamp
from agent_sessions.models import ExtractedSession, SessionMessage, Source
from agent_sessions.render import markdown_for_session
from agent_sessions.utils import slugify

CONTRACT_DIR = Path(__file__).parent / "fixtures" / "contract" / "v1"
SOURCE_FILE_PLACEHOLDER = "__SOURCE_FILE__"
UPDATE = os.environ.get("AGENT_SESSIONS_UPDATE_GOLDENS") == "1"


def _case_dirs() -> list[Path]:
    if not CONTRACT_DIR.exists():
        return []
    return sorted(p for p in CONTRACT_DIR.iterdir() if p.is_dir())


def _render(case: Path, tmp_path: Path) -> tuple[str, dict[str, Any]]:
    data = json.loads((case / "input.json").read_text(encoding="utf-8"))

    # markdown_for_session stat()s the path for its mtime, so we need a real
    # file with a pinned mtime to make "Source modified" deterministic.
    src_file = tmp_path / data["source_file_name"]
    src_file.write_text("fixture", encoding="utf-8")
    os.utime(src_file, (data["mtime"], data["mtime"]))

    source = Source(name=data["source_name"], kind=data["source_kind"], roots=())
    session = ExtractedSession(
        metadata=dict(data["metadata"]),
        messages=[
            SessionMessage(role=m["role"], text=m["text"], timestamp=m.get("timestamp", ""))
            for m in data["messages"]
        ],
    )
    rendered = markdown_for_session(
        source, src_file, session, data["sha256"], imported_at=data["imported_at"]
    )
    rendered = rendered.replace(str(src_file), SOURCE_FILE_PLACEHOLDER)

    yyyymmdd = dt_from_timestamp(data["mtime"])
    session_id = str(session.metadata.get("session_id") or src_file.stem)
    stem = slugify(f"{yyyymmdd}-{session_id}-{src_file.stem}-{data['sha256'][:12]}")
    markdown_rel = f"archive/{data['source_name']}/{stem}.md"
    source_modified = dt.datetime.fromtimestamp(
        data["mtime"], dt.timezone.utc
    ).isoformat(timespec="seconds")

    record = {
        "source": data["source_name"],
        "kind": data["source_kind"],
        "source_file": SOURCE_FILE_PLACEHOLDER,
        "sha256": data["sha256"],
        "size": data["size"],
        "mtime": data["mtime"],
        "messages": len(session.messages),
        "markdown": markdown_rel,
        "metadata": session.metadata,
    }
    derived = {
        "source_modified": source_modified,
        "stem": stem,
        "markdown_rel": markdown_rel,
        "router_index_record": record,
    }
    return rendered, derived


@pytest.mark.parametrize("case", _case_dirs(), ids=lambda p: p.name)
def test_render_matches_golden(case: Path, tmp_path: Path) -> None:
    rendered, derived = _render(case, tmp_path)
    md_golden = case / "expected.md"
    json_golden = case / "expected.json"
    if UPDATE:
        md_golden.write_text(rendered, encoding="utf-8", newline="\n")
        json_golden.write_text(
            json.dumps(derived, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    assert md_golden.read_text(encoding="utf-8") == rendered
    assert json.loads(json_golden.read_text(encoding="utf-8")) == derived


def test_contract_fixtures_present() -> None:
    assert _case_dirs(), "no contract fixtures found under tests/fixtures/contract/v1/"
