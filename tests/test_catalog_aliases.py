"""Content deduplication preserves every still-referenced source path."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

from agent_sessions.archive import index_record_keys, merge_index_records, read_existing_index_records, write_indexes
from agent_sessions.config import ArchiveConfig


def row(path: str, digest: str, source: str = "codex", session_id: str = "shared") -> dict[str, Any]:
    return {"source": source, "kind": "codex", "source_file": path, "sha256": digest,
            "markdown": f"archive/{digest}.md", "metadata": {"session_id": session_id}, "messages": 1}


def paths_by_digest(records: list[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    return {record["sha256"]: set(index_record_keys(record)) for record in records}


def test_changed_alias_retains_old_content_for_other_path_in_every_order() -> None:
    for aliases in itertools.permutations([row("a", "old"), row("b", "old")]):
        for changed in ("a", "b"):
            old = merge_index_records([], list(aliases))
            assert len(old) == 1 and len(index_record_keys(old[0])) == 2
            new = row(changed, "new")
            merged = merge_index_records(old, [new])
            assert paths_by_digest(merged) == {
                "old": {("codex", "b" if changed == "a" else "a")}, "new": {("codex", changed)},
            }
            assert merge_index_records(merged, [new]) == merged
            assert merge_index_records(merged, []) == merged


def test_cached_aliases_cannot_undo_explicit_new_observations() -> None:
    old = merge_index_records([], [row("a", "old"), row("b", "old")])
    for current in itertools.permutations([row("a", "new"), old[0]]):
        merged = merge_index_records(old, list(current))
        assert paths_by_digest(merged) == {"old": {("codex", "b")}, "new": {("codex", "a")}}


def test_last_alias_supersedes_content_and_same_id_forks_survive() -> None:
    old = merge_index_records([], [row("a", "old"), row("b", "old"), row("fork", "fork")])
    changed = merge_index_records(old, [row("a", "new"), row("b", "new")])
    assert paths_by_digest(changed) == {"new": {("codex", "a"), ("codex", "b")}, "fork": {("codex", "fork")}}
    assert merge_index_records(changed, []) == changed


def test_alias_references_survive_catalog_roundtrip_and_remain_portable(tmp_path: Path) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    records = merge_index_records([], [
        row("/home/fixture/.codex/a.jsonl", "old", "linux"),
        row(r"C:\Users\fixture\.codex\a.jsonl", "old", "windows"),
    ])
    write_indexes(config, records)
    restored = read_existing_index_records(config)
    assert index_record_keys(restored[0]) == (
        ("windows", r"~\.codex\a.jsonl"), ("linux", "~/.codex/a.jsonl"),
    )
    assert restored[0]["source_origin"] == "windows-user:C"
    assert restored[0]["source_aliases"][0]["source_origin"] == "posix-home"
    changed = merge_index_records(restored, [row(r"C:\Users\fixture\.codex\a.jsonl", "new", "windows")])
    assert paths_by_digest(changed) == {
        "old": {("linux", "~/.codex/a.jsonl")}, "new": {("windows", r"~\.codex\a.jsonl")},
    }
