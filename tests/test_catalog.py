"""Catalog inspection keeps usable evidence while unsafe writes fail closed."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agent_sessions.archive import (
    export_sources,
    load_index_records,
    pdf_existing,
    prune_index_records,
    read_existing_index_records,
    read_router_index_records,
    select_sources,
    validate_archive_catalog,
    write_indexes,
)
from agent_sessions.archive_stats import archive_statistics
from agent_sessions.catalog import catalog_record_error, parse_catalog_lines, read_catalog
from agent_sessions.collection_health import collection_health
from agent_sessions.config import ArchiveConfig
from agent_sessions.models import Source


def legacy_record() -> dict[str, Any]:
    return {"source": "fixture", "kind": "codex", "source_file": "inputs/a.jsonl", "markdown": "archive/a.md"}


@pytest.mark.parametrize("name", ["index.jsonl", ".router-index.jsonl"])
def test_corrupt_catalog_keeps_good_rows_and_original_bytes(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    config = ArchiveConfig(tmp_path, archive, tmp_path / "raw", ())
    path = archive / name
    payload = (json.dumps(legacy_record()) + '\n{"truncated":\n').encode() + b'\xff\n'
    path.write_bytes(payload)
    reader = read_existing_index_records if name == "index.jsonl" else read_router_index_records
    rows = reader(config)
    assert rows == [legacy_record()]
    health = collection_health(config, rows)
    assert health["indexes"][name] == "malformed"
    assert health["counts_complete"] is False and health["invalid_catalog_rows"] == 2
    assert len(health["catalog_problems"]) == 2
    with pytest.raises(ValueError, match="Original bytes are preserved"):
        validate_archive_catalog(config)
    assert path.read_bytes() == payload
    assert sorted(p.name for p in archive.iterdir()) == [name]
    report = archive_statistics(config)
    assert report["catalog"]["catalog_records"] == 1
    assert report["catalog"]["counts_complete"] is False


@pytest.mark.parametrize("operation", ["export", "prune"])
@pytest.mark.parametrize("name", ["index.jsonl", ".router-index.jsonl"])
@pytest.mark.parametrize("damaged_row", [
    b'{"source":"first","source_file":"inputs/orphan.jsonl"}\n', b'{"truncated":\n',
])
def test_export_and_prune_preserve_invalid_catalogs_before_outputs(
    tmp_path: Path, operation: str, name: str, damaged_row: bytes,
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    transcript = json.dumps({"type": "response_item", "payload": {
        "type": "message", "role": "user", "content": [{"type": "input_text", "text": "synthetic session"}],
    }}) + "\n"
    (inputs / "first.jsonl").write_text(transcript, encoding="utf-8")
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw",
                           (Source("first", "codex", (inputs,), "*.jsonl"),), track_artifacts=True)
    assert export_sources(config, copy_raw_files=True).exported == 1
    catalog = config.archive_dir / name
    valid_catalog = (config.archive_dir / "index.jsonl").read_bytes()
    catalog.write_bytes(valid_catalog + damaged_row)
    if operation == "prune":
        record = read_existing_index_records(config)[0]
        (config.repo_root / record["markdown"]).unlink()
    else:
        (inputs / "second.jsonl").write_text(transcript, encoding="utf-8")
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="Original bytes are preserved"):
        if operation == "export":
            export_sources(config, copy_raw_files=True)
        else:
            prune_index_records(config)
    assert {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("field", ["source", "kind", "source_file", "markdown"])
def test_incomplete_catalog_is_invalid_for_every_reader(tmp_path: Path, field: str) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    config.archive_dir.mkdir()
    record = legacy_record()
    record.pop(field)
    (config.archive_dir / "index.jsonl").write_text(json.dumps(record) + "\n")
    assert read_existing_index_records(config) == load_index_records(config) == []
    health = collection_health(config, [])
    assert health["state"] == "attention_required" and health["counts_complete"] is False
    with pytest.raises(ValueError, match=field):
        validate_archive_catalog(config)


@pytest.mark.parametrize("extra", [
    {"messages": True}, {"messages": -1}, {"size": "1"}, {"mtime": float("inf")}, {"mtime": False},
    {"mtime": 10**400},
    {"metadata": []}, {"sha256": []}, {"pdf": 7}, {"source_origin": {}}, {"parse_status": "unknown"},
    {"malformed_rows": -1}, {"input_records": True}, {"source_aliases": {}},
    {"source_aliases": [{"source": "a"}]},
    {"source_aliases": [{"source": "a", "source_file": "b", "source_origin": {}}]},
    {"markdown": "archive/\x00bad.md"},
])
def test_wrong_catalog_field_types_are_rejected(extra: dict[str, Any]) -> None:
    assert catalog_record_error({**legacy_record(), **extra}) is not None


def test_legacy_optional_fields_and_router_records_remain_writable(tmp_path: Path) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    config.archive_dir.mkdir()
    record = legacy_record()
    write_indexes(config, [record])
    assert "unknown" in (config.archive_dir / "INDEX.md").read_text()
    (config.archive_dir / ".router-index.jsonl").write_text(json.dumps({
        **record, "kind": "copilot_chat", "metadata": {}, "messages": 0, "sha256": "legacy-digest",
        "mtime": 0.0, "pdf": None, "raw": None, "source_origin": "windows-user:C",
    }) + "\n")
    validate_archive_catalog(config)
    assert len(read_router_index_records(config)) == 1


def test_pdf_rewrite_refuses_schema_invalid_catalog_before_outputs(tmp_path: Path) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    config.archive_dir.mkdir()
    path = config.archive_dir / "index.jsonl"
    payload = b'{"source":"fixture","source_file":"a"}\n'
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="missing required field"):
        pdf_existing(config)
    assert path.read_bytes() == payload
    assert list(config.archive_dir.iterdir()) == [path]


def test_missing_and_unreadable_catalogs_are_distinct(tmp_path: Path) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    validate_archive_catalog(config)
    assert read_catalog(config.archive_dir / "index.jsonl").state == "missing"
    (config.archive_dir / "index.jsonl").mkdir(parents=True)
    with pytest.raises(ValueError, match="unreadable"):
        validate_archive_catalog(config)


@pytest.mark.parametrize("failure", [OSError, EOFError])
def test_midstream_read_failure_retains_already_read_evidence(failure: type[Exception]) -> None:
    def lines() -> Iterator[bytes]:
        yield (json.dumps(legacy_record()) + "\n").encode()
        raise failure("synthetic interruption")

    result = parse_catalog_lines(lines(), "fixture")
    assert result.records == [legacy_record()] and result.state == "unreadable"
    assert result.invalid_rows == 0 and len(result.problems) == 1


def test_all_unmatched_selectors_fail_without_creating_archive(archive_config: ArchiveConfig) -> None:
    before = sorted(str(path) for path in archive_config.repo_root.rglob("*"))
    with pytest.raises(ValueError, match="No configured sources matched"):
        export_sources(archive_config, selected=["typo"])
    assert sorted(str(path) for path in archive_config.repo_root.rglob("*")) == before


def test_mixed_selectors_warn_and_keep_valid_empty_source(
    archive_config: ArchiveConfig, capsys: pytest.CaptureFixture[str],
) -> None:
    sources = select_sources(archive_config, ["typo", "claude"])
    assert sources == list(archive_config.sources)
    assert "'typo' matched no configured" in capsys.readouterr().err
    assert export_sources(archive_config, selected=["claude"]).exported == 0


@pytest.mark.parametrize("extra,complete", [
    ({"parse_status": "partial"}, False), ({"malformed_rows": 1}, False), ({"parse_status": "empty"}, True),
])
def test_source_parse_diagnostics_produce_honest_health(
    tmp_path: Path, extra: dict[str, Any], complete: bool,
) -> None:
    config = ArchiveConfig(tmp_path, tmp_path / "archive", tmp_path / "raw", ())
    config.archive_dir.mkdir()
    (config.archive_dir / "a.md").write_text("_No messages._")
    record = {**legacy_record(), "messages": 0, **extra}
    write_indexes(config, [record])
    health = collection_health(config, [record])
    assert health["state"] == "attention_required" and health["counts_complete"] is complete
    assert health["problems"]
