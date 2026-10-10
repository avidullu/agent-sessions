"""Synthetic regression coverage for archive publication and source integrity."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import stat
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

    def changing_source(staged: Path, *, source_path: Path | None = None) -> ExtractedSession:
        session(source, "after")
        return extract(staged, source_path=source_path)

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

    def paused_extract(path: Path, *, source_path: Path | None = None) -> ExtractedSession:
        entered.set()
        assert release.wait(timeout=10)
        return original(path, source_path=source_path)

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
        if os.name == "nt":
            with pytest.raises(PermissionError):
                lock.rename(tmp_path / "old-lock")
        else:
            lock.rename(tmp_path / "old-lock")
            lock.write_text("replacement")
    if os.name == "nt":
        assert not lock.exists()
    else:
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
        if os.name == "nt":
            with pytest.raises(PermissionError):
                (tmp_path / ".archive-write.lock").unlink()
        else:
            (tmp_path / ".archive-write.lock").unlink()
    assert not (tmp_path / ".archive-write.lock").exists()


@pytest.mark.parametrize("catalog_name", ["index.jsonl", ".router-index.jsonl"])
@pytest.mark.parametrize("operation", ["export", "prune", "pdf"])
def test_catalog_writers_preserve_corruption_and_refuse_before_artifacts(
    tmp_path: Path, catalog_name: str, operation: str
) -> None:
    from dataclasses import replace

    from agent_sessions.archive import pdf_existing, prune_index_records

    config = replace(configuration(tmp_path), track_artifacts=True)
    session(tmp_path / "inputs/s.jsonl", "hello")
    export_sources(config)
    catalog = config.archive_dir / catalog_name
    previous = catalog.read_bytes() if catalog.exists() else b""
    damaged = previous + b"{truncated\n"
    catalog.write_bytes(damaged)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="Original bytes are preserved"):
        if operation == "export":
            export_sources(config)
        elif operation == "prune":
            prune_index_records(config)
        else:
            pdf_existing(config)
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_cached_alias_does_not_overwrite_a_changed_primary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_sessions.archive import index_record_key, index_record_keys, sha256_file

    config = configuration(tmp_path)
    a, b = tmp_path / "inputs/a.jsonl", tmp_path / "inputs/b.jsonl"
    session(a, "old")
    b.write_bytes(a.read_bytes())
    stat = a.stat()
    os.utime(b, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    export_sources(config)
    initial = read_existing_index_records(config)
    assert len(initial) == 1 and len(index_record_keys(initial[0])) == 2
    session(b, "new")
    monkeypatch.setattr("agent_sessions.archive.iter_source_files", lambda _source: iter([b, a]))
    export_sources(config)
    rows = read_existing_index_records(config)
    assert len(rows) == 2
    by_key = {key: row for row in rows for key in index_record_keys(row)}
    assert by_key[index_record_key({"source": "first", "source_file": str(a)})]["sha256"] == sha256_file(a)
    assert by_key[index_record_key({"source": "first", "source_file": str(b)})]["sha256"] == sha256_file(b)


def test_status_does_not_count_missing_alias_as_missing_session(tmp_path: Path) -> None:
    from agent_sessions.archive_status import status_summary

    config = configuration(tmp_path)
    a, b = tmp_path / "inputs/a.jsonl", tmp_path / "inputs/b.jsonl"
    session(a, "hello")
    b.write_bytes(a.read_bytes())
    export_sources(config)
    b.unlink()
    report = status_summary(config)
    assert report.indexed_records == 1 and report.visible_files == 1
    assert report.not_visible_records == 0 and report.new_files == 0


def test_unbound_existing_artifact_is_preserved(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    session(tmp_path / "inputs/s.jsonl", "hello")
    export_sources(config)
    row = read_existing_index_records(config)[0]
    target = tmp_path / row["markdown"]
    (config.archive_dir / "index.jsonl").unlink()
    target.write_text("synthetic owner notes\n")
    with pytest.raises(ValueError, match="no valid source binding"):
        export_sources(config)
    assert target.read_text() == "synthetic owner notes\n"


def test_sanitized_short_names_preserve_distinct_session_identities(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    content = '{"type":"response_item","payload":{"role":"user","content":"hello"}}\n'
    for name in ("a b.jsonl", "a-b.jsonl"):
        (tmp_path / "inputs" / name).write_text(content)
    result = export_sources(config)
    rows = read_existing_index_records(config)
    assert result.exported == 2 and len(rows) == 2
    assert len({row["markdown"] for row in rows}) == 2
    for row in rows:
        assert f"# first / {row['metadata']['session_id']}\n" in (tmp_path / row["markdown"]).read_text()
    assert export_sources(config).exported == 2


def test_raw_copy_accepts_long_legal_input_name(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs" / ("x" * 235 + ".jsonl")
    session(source, "hello")
    result = export_sources(config, copy_raw_files=True)
    row = read_existing_index_records(config)[0]
    assert result.exported == 1 and not result.deferred_files
    target = tmp_path / row["raw"]
    assert len(target.name.encode()) <= 255
    assert gzip.decompress(target.read_bytes()) == source.read_bytes()


@pytest.mark.parametrize("kind", ["codex", "claude", "grok", "gemini_antigravity"])
def test_unsupported_provider_shape_has_distinct_reason(tmp_path: Path, kind: str) -> None:
    from dataclasses import replace

    config = configuration(tmp_path)
    config = replace(config, sources=(replace(config.sources[0], kind=kind),))
    (tmp_path / "inputs/s.jsonl").write_text('{"unexpected_schema":true}\n')
    result = export_sources(config)
    row = read_existing_index_records(config)[0]
    assert result.unsupported_files == 1 and result.malformed_files == 0
    assert row["parse_status"] == "partial" and row["empty_reason"] == "unsupported_schema"


def test_legal_metadata_only_has_distinct_reason(tmp_path: Path) -> None:
    config = configuration(tmp_path)
    (tmp_path / "inputs/s.jsonl").write_text('{"type":"session_meta","payload":{"id":"empty"}}\n')
    result = export_sources(config)
    row = read_existing_index_records(config)[0]
    assert not result.unsupported_files
    assert row["parse_status"] == "empty" and row["empty_reason"] == "metadata_only"


def test_atomic_flush_failure_preserves_old_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "index.jsonl"
    target.write_text("prior bytes\n")

    def refuse_flush(_descriptor: int) -> None:
        raise OSError("synthetic flush failure")

    monkeypatch.setattr("agent_sessions.archive_io.os.fsync", refuse_flush)
    with pytest.raises(OSError, match="flush failure"):
        write_text_if_changed(target, "prepared bytes\n")
    assert target.read_text() == "prior bytes\n"
    assert not list(tmp_path.glob(".pending-*"))


def test_atomic_publication_satisfies_writable_handle_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "artifact.md"
    target.write_text("prior")
    original_fsync = os.fsync
    file_flushes: list[int] = []

    def require_writable_file(descriptor: int) -> None:
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            # Emulate Windows _commit: a read-only descriptor fails this check.
            os.write(descriptor, b"")
            file_flushes.append(descriptor)
        original_fsync(descriptor)

    monkeypatch.setattr("agent_sessions.archive_io.os.fsync", require_writable_file)
    assert write_text_if_changed(target, "published")
    assert file_flushes and target.read_text() == "published"
    assert not list(tmp_path.glob(".pending-*"))


def test_capture_accepts_rewritten_stable_source(tmp_path: Path) -> None:
    source = tmp_path / "session.jsonl"
    session(source, "original")
    for number in range(5):
        session(source, f"rewritten {number}")
        expected = source.read_bytes()
        with capture_source(source) as captured:
            assert captured.path.read_bytes() == expected
            assert captured.digest == hashlib.sha256(expected).hexdigest()


def test_capture_refuses_change_within_open_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_sessions.archive_io import SourceChangingError

    source = tmp_path / "session.jsonl"
    session(source, "same")
    original_fstat = os.fstat
    counter = iter(range(20))

    def changing_fstat(descriptor: int) -> os.stat_result:
        observed = original_fstat(descriptor)
        extras = {"st_mtime_ns": observed.st_mtime_ns, "st_ctime_ns": observed.st_ctime_ns + next(counter)}
        birth_time = getattr(observed, "st_birthtime_ns", None)
        if birth_time is not None:
            extras["st_birthtime_ns"] = int(birth_time)
        return os.stat_result(tuple(observed), extras)

    monkeypatch.setattr("agent_sessions.archive_io.os.fstat", changing_fstat)
    with pytest.raises(SourceChangingError):
        with capture_source(source):
            pytest.fail("changed descriptor must not publish a snapshot")


@pytest.mark.parametrize("available", [True, False])
def test_windows_change_time_query_returns_kernel_value_or_refuses(
    monkeypatch: pytest.MonkeyPatch, available: bool
) -> None:
    import ctypes
    import sys
    from typing import Any
    from unittest.mock import MagicMock

    from agent_sessions.archive_io import windows_change_time

    def query(handle: int, info_class: int, pointer: Any, size: int) -> int:
        assert handle == 123 and info_class == 0 and size == 40
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int64))[3] = 456
        return int(available)

    function = MagicMock(side_effect=query)
    kernel = MagicMock(GetFileInformationByHandleEx=function)
    loader = MagicMock(return_value=kernel)
    monkeypatch.setattr(ctypes, "WinDLL", loader, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    monkeypatch.setitem(sys.modules, "msvcrt", MagicMock(get_osfhandle=lambda _descriptor: 123))
    if available:
        assert windows_change_time(7) == 456
    else:
        with pytest.raises(OSError, match="observation unavailable"):
            windows_change_time(7)
    loader.assert_called_once_with("kernel32", use_last_error=True)
    assert function.argtypes == (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
    assert function.restype == ctypes.c_int


@pytest.mark.parametrize("kind,original", [
    ("grok", "/dir/session.jsonl"),
    ("gemini_antigravity", "/dir/session/session.jsonl"),
    ("gemini_antigravity", "/dir/session.jsonl"),
    ("claude", "/dir/session.jsonl"),
    ("deepseek_request_dump", "/dir/session.jsonl"),
    ("codex", "/dir/session.jsonl"),
])
def test_snapshot_identity_uses_original_shallow_path(tmp_path: Path, kind: str, original: str) -> None:
    from agent_sessions.sources.registry import get_extractor

    extractor = get_extractor(kind)
    assert extractor is not None
    staged = tmp_path / "capture/project/session/staged.jsonl"
    staged.parent.mkdir(parents=True)
    staged.write_text('{"source":"user","type":"user","content":"first"}\n')
    identity = Path(original)
    # The identity path deliberately does not exist: only captured bytes are read.
    expected = extractor(staged, source_path=identity).metadata
    staged.write_text('{"source":"user","type":"user","content":"second"}\n')
    assert extractor(staged, source_path=identity).metadata == expected
    if kind == "grok":
        assert expected == {"session_id": identity.parent.name, "project": identity.parent.parent.name}
    elif kind == "gemini_antigravity":
        assert expected["session_id"] == ((identity.parents[2].name if len(identity.parents) > 2 else "") or identity.stem)
    assert "capture" not in json.dumps(expected)


@pytest.mark.parametrize("kind", ["grok", "gemini_antigravity"])
def test_export_keeps_provider_identity_after_source_edit(tmp_path: Path, kind: str) -> None:
    from agent_sessions.sources.registry import get_extractor

    config = configuration(tmp_path)
    source = tmp_path / "inputs/session.jsonl"
    config = ArchiveConfig(config.repo_root, config.archive_dir, config.raw_dir,
                           (Source("first", kind, (source.parent,), "*.jsonl"),))
    extractor = get_extractor(kind)
    assert extractor is not None
    rows = []
    for text in ("first", "second"):
        source.write_text(json.dumps({"source": "user", "type": "user", "content": text}) + "\n")
        expected = extractor(source).metadata
        export_sources(config)
        rows.append(read_existing_index_records(config)[0])
        assert rows[-1]["metadata"] == expected
        assert "agent-archive-capture-" not in (tmp_path / rows[-1]["markdown"]).read_text()
    assert rows[0]["metadata"] == rows[1]["metadata"]
    # Digest-addressed old versions remain available by design, with stable titles.
    assert rows[0]["markdown"] != rows[1]["markdown"]
    export_sources(config)
    assert len(list(config.archive_dir.rglob("*.md"))) == 3  # two versions plus INDEX.md


@pytest.mark.parametrize("item_type", [
    "web_search_call", "local_shell_call", "image_generation_call", "tool_search_call",
    "tool_search_output", "additional_tools", "compaction", "compaction_summary",
    "context_compaction", "configuration_update", "compaction_trigger",
])
def test_known_codex_non_transcript_items_do_not_fail_export(
    tmp_path: Path, item_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_sessions.cli import main

    config = configuration(tmp_path)
    source = tmp_path / "inputs/session.jsonl"
    session(source, "archived user message")
    with source.open("a") as stream:
        stream.write(json.dumps({"type": "response_item", "payload": {"type": item_type}}) + "\n")
    monkeypatch.setattr("agent_sessions.cli.load_config", lambda *_args, **_kwargs: config)
    assert main(["--repo-root", str(tmp_path), "export", "--all"]) == 0
    row = read_existing_index_records(config)[0]
    assert row["parse_status"] == "complete"
    assert row["unsupported_rows"] == 0
    assert row["messages"] == 1


@pytest.mark.parametrize("kind", ["gemini_antigravity", "codex"])
def test_rc1_cached_extraction_is_refreshed_without_source_edits(tmp_path: Path, kind: str) -> None:
    config = configuration(tmp_path)
    source = tmp_path / "inputs/session.jsonl"
    config = ArchiveConfig(config.repo_root, config.archive_dir, config.raw_dir,
                           (Source("first", kind, (source.parent,), "*.jsonl"),))
    if kind == "codex":
        session(source, "hello")
        with source.open("a") as stream:
            stream.write('{"type":"response_item","payload":{"type":"web_search_call"}}\n')
    else:
        source.write_text('{"source":"user","content":"hello"}\n')
    export_sources(config)
    row = read_existing_index_records(config)[0]
    expected_metadata = row["metadata"]
    row.pop("extractor_revision")
    if kind == "codex":
        row.update(parse_status="partial", unsupported_rows=1)
    else:
        row["metadata"] = {"session_id": "agent-archive-capture-obsolete"}
    (config.archive_dir / "index.jsonl").write_text(json.dumps(row) + "\n")
    result = export_sources(config)
    refreshed = read_existing_index_records(config)[0]
    assert not result.unsupported_files
    assert refreshed["metadata"] == expected_metadata
    assert refreshed["parse_status"] == "complete"
    assert refreshed["extractor_revision"] == 1
