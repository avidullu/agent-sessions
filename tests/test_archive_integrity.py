"""Synthetic regression coverage for archive publication and source integrity."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from agent_sessions.archive import export_sources, read_existing_index_records, write_text_if_changed
from agent_sessions.archive_io import archive_writer, artifact_stem, capture_source
from agent_sessions.config import ArchiveConfig
from agent_sessions.models import ExtractedSession, Source
from agent_sessions.sources.codex import extract


def configuration(root: Path) -> ArchiveConfig:
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    return ArchiveConfig(root, root / "archive", root / "raw", (Source("first", "codex", (inputs,), "*.jsonl"),))


def session(path: Path, text: str, identity: str = "synthetic") -> None:
    path.write_text(json.dumps({"type": "session_meta", "payload": {"id": identity}}) + "\n"
                    + json.dumps({"type": "response_item", "payload": {"role": "user", "content": text}}) + "\n",
                    encoding="utf-8")


def test_dry_run_has_no_workspace_writes(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    session(tmp_path / "inputs/s.jsonl", "hello")
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    export_sources(config, dry_run=True, copy_raw_files=True, write_pdfs=True)
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before


def test_capture_binds_render_and_raw_to_copied_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs/s.jsonl"
    session(source, "before")
    expected = source.read_bytes()

    def changing_source(staged: Path) -> ExtractedSession:
        session(source, "after")
        return extract(staged)

    monkeypatch.setattr("agent_sessions.archive.get_extractor", lambda _kind: changing_source)
    result = export_sources(config, copy_raw_files=True)
    row = read_existing_index_records(config)[0]
    assert not result.deferred_files
    raw = gzip.decompress((tmp_path / row["raw"]).read_bytes())
    assert raw == expected
    assert row["sha256"] == hashlib.sha256(raw).hexdigest()
    rendered = (tmp_path / row["markdown"]).read_text()
    assert "before" in rendered and "after" not in rendered
    assert str(source) in rendered
    assert "agent-archive-capture-" not in rendered


def test_snapshot_preserves_provider_ancestry_and_timestamp(tmp_path: Path) -> None:
    source = tmp_path / "project/session/subagents/a.jsonl"
    source.parent.mkdir(parents=True)
    session(source, "hello")
    stat = source.stat()
    with capture_source(source) as captured:
        assert captured.path.name == source.name
        assert [p.name for p in captured.path.parents[:3]] == [p.name for p in source.parents[:3]]
        assert captured.path.stat().st_mtime_ns == stat.st_mtime_ns
        assert captured.path.read_bytes() == source.read_bytes()
        assert captured.stat.st_mtime_ns == stat.st_mtime_ns


def test_long_names_keep_digest_and_previous_artifact(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs" / ("x" * 110 + ".jsonl")
    session(source, "one")
    export_sources(config)
    first = read_existing_index_records(config)[0]
    session(source, "two")
    export_sources(config)
    second = read_existing_index_records(config)[0]
    assert first["markdown"] != second["markdown"]
    assert (tmp_path / first["markdown"]).exists()
    assert Path(second["markdown"]).stem.endswith(second["sha256"][:12])
    assert len(Path(second["markdown"]).stem) <= 90


def test_long_names_with_equal_prefix_and_bytes_are_distinct() -> None:
    digest = "a" * 64
    first = artifact_stem("20261010", "same", "x" * 110 + "a", digest)
    second = artifact_stem("20261010", "same", "x" * 110 + "b", digest)
    assert first != second
    assert first.endswith(digest[:12]) and second.endswith(digest[:12])


def test_same_size_head_change_restored_mtime_is_not_reused(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs/s.jsonl"
    session(source, "A" + "x" * 70000)
    export_sources(config)
    first = read_existing_index_records(config)[0]
    stat = source.stat()
    source.write_text(source.read_text().replace("A", "B", 1))
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    export_sources(config)
    second = read_existing_index_records(config)[0]
    assert second["sha256"] != first["sha256"]
    assert second["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_concurrent_writer_refuses_then_retry_preserves_both_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    config = configuration(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    session(tmp_path / "inputs/a.jsonl", "source a", "a")
    session(other / "b.jsonl", "source b", "b")
    config = replace(config, sources=config.sources + (Source("other", "codex", (other,), "*.jsonl"),))
    entered, release = threading.Event(), threading.Event()
    errors: list[Exception] = []
    original = extract

    def paused_extract(path: Path) -> ExtractedSession:
        entered.set()
        assert release.wait(timeout=10)
        return original(path)

    def first_writer() -> None:
        try:
            export_sources(config, selected=["first"])
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr("agent_sessions.archive.get_extractor", lambda _kind: paused_extract)
    thread = threading.Thread(target=first_writer)
    thread.start()
    try:
        assert entered.wait(timeout=10)
        with pytest.raises(ValueError, match="writer lock"):
            export_sources(config, selected=["other"])
    finally:
        release.set()
        thread.join(timeout=10)
    assert not errors and not thread.is_alive()
    export_sources(config, selected=["other"])
    assert len(read_existing_index_records(config)) == 2
    assert not (config.archive_dir / ".archive-write.lock").exists()


def test_writer_does_not_remove_replacement_lock(tmp_path: Path) -> None:
    with archive_writer(tmp_path):
        lock = tmp_path / ".archive-write.lock"
        lock.rename(tmp_path / "old-lock")
        lock.write_text("replacement")
    assert lock.read_text() == "replacement"


def test_atomic_write_failure_preserves_previous_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "index.jsonl"
    target.write_text("old\n")

    def refuse_replace(_old: Path, _new: Path) -> None:
        raise OSError("synthetic disk failure")

    monkeypatch.setattr("agent_sessions.archive_io.os.replace", refuse_replace)
    with pytest.raises(OSError, match="disk failure"):
        write_text_if_changed(target, "new\n")
    assert target.read_text() == "old\n"
    assert not list(tmp_path.glob(".pending-*"))


def test_malformed_source_is_partial_and_valid_messages_survive(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs/s.jsonl"
    session(source, "good")
    with source.open("a") as stream:
        stream.write("{truncated\n")
    result = export_sources(config)
    row = read_existing_index_records(config)[0]
    assert result.malformed_files == 1
    assert row["parse_status"] == "partial" and row["malformed_rows"] == 1
    assert row["messages"] == 1 and "good" in (tmp_path / row["markdown"]).read_text()


def test_metadata_only_is_explicitly_empty(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    (tmp_path / "inputs/s.jsonl").write_text('{"type":"session_meta","payload":{"id":"empty"}}\n')
    result = export_sources(config)
    assert result.empty_files == 1
    assert read_existing_index_records(config)[0]["parse_status"] == "empty"


def test_source_that_never_settles_is_deferred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_sessions import archive_io

    config = configuration(tmp_path)
    source = tmp_path / "inputs/s.jsonl"
    session(source, "hello")
    counter = iter(range(100))

    def unstable_signature(stat: os.stat_result) -> tuple[int, int, int, int]:
        return stat.st_size, stat.st_mtime_ns, next(counter), stat.st_ino

    monkeypatch.setattr(archive_io, "signature", unstable_signature)
    result = export_sources(config)
    assert result.exported == 0 and result.deferred_files == ("first: changing_source",)
    assert not list(config.archive_dir.glob("first/*.md"))
    assert read_existing_index_records(config) == []


def test_invalid_utf8_is_diagnosed_not_silently_replaced(tmp_path: Path) -> None:
    source = tmp_path / "s.jsonl"
    source.write_bytes(b'{"type":"message","payload":{"role":"user","content":"bad\xff"}}\n')
    parsed = extract(source)
    assert parsed.malformed_rows == 1 and not parsed.messages


def test_unavailable_source_preserves_prior_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    from agent_sessions.archive_io import CapturedSource

    config = configuration(tmp_path)
    session(tmp_path / "inputs/s.jsonl", "old")
    export_sources(config)
    original = (config.archive_dir / "index.jsonl").read_bytes()

    @contextmanager
    def unavailable(_path: Path) -> Iterator[CapturedSource]:
        raise OSError("synthetic source rotation")
        yield  # pragma: no cover

    monkeypatch.setattr("agent_sessions.archive.capture_source", unavailable)
    result = export_sources(config)
    assert result.deferred_files == ("first: source_or_output_unavailable",)
    assert (config.archive_dir / "index.jsonl").read_bytes() == original


def test_cli_partial_export_returns_nonzero_with_actionable_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from agent_sessions.cli import main

    config = configuration(tmp_path)
    root = config.sources[0].roots[0]
    (tmp_path / "sources.toml").write_text(
        '[[sources]]\nname="first"\nkind="codex"\nglob="*.jsonl"\nroots=[' + json.dumps(str(root)) + ']\n'
    )
    (root / "s.jsonl").write_text('{truncated\n{"type":"session_meta","payload":{"id":"empty"}}\n')
    assert main(["--repo-root", str(tmp_path), "export", "--all"]) == 1
    output = capsys.readouterr().out
    assert "Partial export" in output and "no transcript messages" in output


def test_nonobject_provider_row_is_diagnosed(tmp_path: Path) -> None:
    source = tmp_path / "s.jsonl"
    source.write_text('["invalid-row"]\n')
    assert extract(source).malformed_rows == 1


def test_format_v2_long_naming_goldens() -> None:
    fixture = Path(__file__).parent / "fixtures/contract/v2/long-naming.json"
    cases = json.loads(fixture.read_text())["cases"]
    for case in cases:
        assert artifact_stem(case["date"], case["session_id"], case["filename"], case["sha256"]) == case["expected_stem"]


def test_status_verify_detects_head_edit_hidden_from_fast_status(tmp_path: Path) -> None:
    from agent_sessions.archive_status import status_summary, status_to_dict

    config = configuration(tmp_path)
    source = tmp_path / "inputs/s.jsonl"
    session(source, "A" + "x" * 70000)
    export_sources(config)
    stat = source.stat()
    source.write_text(source.read_text().replace("A", "B", 1))
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    fast = status_summary(config)
    checked = status_summary(config, verify_content=True)
    assert fast.changed_files == 0 and fast.content_check == "metadata_and_tail"
    assert checked.changed_files == 1 and status_to_dict(checked)["content_check"] == "full_sha256"


def test_export_reparses_legacy_cache_to_report_damage(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs/s.jsonl"
    session(source, "good")
    with source.open("a") as stream:
        stream.write("{truncated\n")
    export_sources(config)
    row = read_existing_index_records(config)[0]
    for key in ("format_version", "parse_status", "malformed_rows", "input_records"):
        row.pop(key)
    (config.archive_dir / "index.jsonl").write_text(json.dumps(row) + "\n")
    assert export_sources(config).malformed_files == 1
    assert read_existing_index_records(config)[0]["parse_status"] == "partial"


def test_writer_cleanup_tolerates_already_removed_lock(tmp_path: Path) -> None:
    with archive_writer(tmp_path):
        (tmp_path / ".archive-write.lock").unlink()
    assert not (tmp_path / ".archive-write.lock").exists()
