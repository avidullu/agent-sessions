"""Bounded, offline metadata seam between the archive and Bheem observations.

Never execute a manifest action, inspect transcripts, fetch dependencies, or infer
resource savings from archive counts. All imported observations remain unsigned.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

from .archive import merge_index_records
from .catalog import CATALOG_NAMES, CatalogRead, parse_catalog_lines
from .collection_health import collection_health
from .config import ArchiveConfig
from .sources.registry import known_kinds

SCHEMA = "agent-sessions.efficiency-report.v1"
BINDING_SCHEMA = "agent-sessions.bheem-bindings.v1"
MAX_BYTES = 1 << 20
MAX_CATALOG_BYTES = 16 << 20
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
SCOPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
GIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
# Markers are refused without echoing either the input or a matched value.
SENSITIVE = re.compile(
    r"Bearer\s+|ghp_|github_pat_|AKIA[0-9A-Z]{16}|-----BEGIN .*PRIVATE KEY|"
    r"[A-Za-z0-9-]+\.(?:tail[0-9a-f]+\.)?ts\.net\b|"
    r"(?:/home/|/Users/|[A-Za-z]:[\\/]Users[\\/]|/mnt/[A-Za-z]/Users/)|"
    r"\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
IDENTITY_KEYS = (
    "repository",
    "pr_number",
    "recipe",
    "workflow",
    "source_sha",
    "base_sha",
    "recipe_digest",
    "toolchain_digest",
    "dependency_digest",
    "configuration_digest",
    "required_contexts",
)
RUN_IDENTITY_KEYS = (
    "repository",
    "source_sha",
    "base_sha",
    "recipe_digest",
    "toolchain_digest",
    "dependency_digest",
    "configuration_digest",
)
ACTIONS = {"select", "defer", "supersede", "cancel-candidate"}
COLLECTION_KEYS = (
    "state",
    "sessions",
    "messages",
    "counts_complete",
    "invalid_catalog_rows",
    "sessions_with_partial_parse",
    "empty_source_files",
    "sessions_with_unknown_message_count",
    "local_markdown_bytes",
    "missing_local_artifacts",
    "last_successful_export",
    "indexes",
    "sources",
)


class EvidenceRejected(ValueError):
    """Safe, constant diagnostics: never include raw input or local paths."""


def _object(value: Any, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(required) <= value.keys() or not value.keys() <= set(required + optional):
        raise EvidenceRejected("unsupported object fields")
    return value


def _items(value: Any, maximum: int = 256) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise EvidenceRejected("unsupported list size")
    return value


def _number(value: Any, nullable: bool = False) -> int | float | None:
    if value is None and nullable:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
        or value > 2**63 - 1
        or not math.isfinite(value)
    ):
        raise EvidenceRejected("invalid nonnegative number")
    return value


def _count(value: Any, nullable: bool = False) -> int | None:
    _number(value, nullable)
    if value is not None and (not isinstance(value, int) or value > 2**63 - 1):
        raise EvidenceRejected("invalid integer count")
    return value


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise EvidenceRejected("invalid boolean")
    return value


def _text(value: Any, pattern: re.Pattern[str] | None = None, maximum: int = 512, empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (not empty and not value)
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or SENSITIVE.search(value)
        or (pattern is not None and not pattern.fullmatch(value))
    ):
        raise EvidenceRejected("invalid or sensitive metadata string")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise EvidenceRejected("invalid metadata encoding") from None
    return value


def timestamp(value: Any) -> dt.datetime:
    _text(value, maximum=40)
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceRejected("invalid timestamp") from None
    if result.tzinfo is None or result.utcoffset() != dt.timedelta(0):
        raise EvidenceRejected("timestamps require explicit UTC")
    return result.astimezone(dt.UTC)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceRejected("duplicate JSON field")
        result[key] = value
    return result


def _constant(_raw: str) -> Any:
    raise EvidenceRejected("nonfinite JSON number")


def _walk(value: Any, depth: int = 0) -> None:
    if depth > 16:
        raise EvidenceRejected("JSON nesting exceeds bound")
    if isinstance(value, dict):
        if len(value) > 64:
            raise EvidenceRejected("JSON object exceeds bound")
        for key, item in value.items():
            _text(key, maximum=64)
            if key.casefold() in {
                "content",
                "prompt",
                "messages_text",
                "authorization",
                "token",
                "secret",
                "transcript",
            }:
                raise EvidenceRejected("forbidden private field")
            _walk(item, depth + 1)
    elif isinstance(value, list):
        for item in _items(value, 4096):
            _walk(item, depth + 1)
    elif isinstance(value, str):
        _text(value, maximum=1000, empty=True)
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise EvidenceRejected("unsupported JSON value")
    elif isinstance(value, float) and not math.isfinite(value):
        raise EvidenceRejected("nonfinite JSON number")


def read_bytes(path: Path, maximum: int = MAX_BYTES) -> bytes:
    """Refuse links, special files, changed inode and oversize before parsing."""
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum or before.st_nlink != 1:
            raise EvidenceRejected("input must be a bounded regular file with one link")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            current = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_size > maximum
                or current.st_nlink != 1
                or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
            ):
                raise EvidenceRejected("input changed during open")
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise EvidenceRejected("input exceeds byte bound")
        return raw
    except OSError:
        raise EvidenceRejected("input is unavailable") from None


def load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(read_bytes(path), object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise EvidenceRejected("invalid JSON") from None
    _walk(document)
    if not isinstance(document, dict):
        raise EvidenceRejected("expected a JSON object")
    return document


def identity(value: Any) -> dict[str, Any]:
    raw = _object(value, IDENTITY_KEYS)
    repository = _text(raw["repository"], maximum=193)
    if len(repository.split("/")) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,95}", p) or ".." in p or p.endswith(".")
        for p in repository.split("/")
    ):
        raise EvidenceRejected("invalid repository identity")
    if not _count(raw["pr_number"]):
        raise EvidenceRejected("positive PR number required")
    for key in ("recipe", "workflow"):
        _text(raw[key], NAME)
    if not raw["workflow"].endswith((".yml", ".yaml")):
        raise EvidenceRejected("workflow YAML basename required")
    for key in ("source_sha", "base_sha"):
        value = _text(raw[key], GIT)
        if not value.strip("0"):
            raise EvidenceRejected("zero Git object ID refused")
    if len(raw["source_sha"]) != len(raw["base_sha"]):
        raise EvidenceRejected("Git object formats differ")
    for key in IDENTITY_KEYS[6:10]:
        _text(raw[key], DIGEST)
    contexts = [_text(item, maximum=160) for item in _items(raw["required_contexts"], 64)]
    if not contexts or len(contexts) != len(set(contexts)) or any(item.strip() != item for item in contexts):
        raise EvidenceRejected("distinct required contexts needed")
    return {key: sorted(contexts) if key == "required_contexts" else raw[key] for key in IDENTITY_KEYS}


def checkpoint_id(value: Any) -> str:
    # Match Go's typed struct order, sorted contexts and json.Marshal escaping.
    raw = json.dumps(identity(value), ensure_ascii=False, separators=(",", ":"))
    for char, escaped in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        raw = raw.replace(char, escaped)
    return hashlib.sha256(raw.encode()).hexdigest()


def collection_snapshot(config: ArchiveConfig) -> dict[str, Any]:
    """Existing health API, with bounded catalogs and no raw provider traversal."""
    catalogs: dict[str, CatalogRead] = {}
    for name in CATALOG_NAMES:
        path = config.archive_dir / name
        if not path.exists() and not path.is_symlink():
            catalogs[name] = CatalogRead(missing=True)
            continue
        try:
            catalogs[name] = parse_catalog_lines(read_bytes(path, MAX_CATALOG_BYTES).splitlines(), name)
        except EvidenceRejected:
            catalogs[name] = CatalogRead(unreadable=True)
    records = merge_index_records(catalogs[CATALOG_NAMES[0]].records, catalogs[CATALOG_NAMES[1]].records)
    health = collection_health(config, records, catalogs=catalogs)
    result = {key: health[key] for key in COLLECTION_KEYS if key != "sources"}
    # Names are configured free text and can contain private identities. Publish
    # stable-within-this-configuration ordinal aliases and known provider kinds.
    kinds = known_kinds()
    result["sources"] = [
        {
            "source_id": f"source-{index + 1:03}",
            "kind": source.kind if source.kind in kinds else "inventory",
            "state": health["sources"][source.name],
        }
        for index, source in enumerate((*config.sources, *config.disabled_sources))
    ]
    return result


def load_bindings(document: dict[str, Any], now: dt.datetime) -> list[dict[str, Any]]:
    _object(document, ("schema", "generated_at", "bindings"))
    if document["schema"] != BINDING_SCHEMA or timestamp(document["generated_at"]) > now:
        raise EvidenceRejected("unsupported or future binding manifest")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in _items(document["bindings"]):
        row = _object(value, ("session_id", "worktree_id", "checkpoint_id", "identity", "package"))
        for key in ("session_id", "worktree_id"):
            _text(row[key], ID)
        ident = identity(row["identity"])
        cid = _text(row["checkpoint_id"], HEX)
        if cid != checkpoint_id(ident) or cid in seen:
            raise EvidenceRejected("checkpoint identity mismatch or repeated binding")
        seen.add(cid)
        package = row["package"]
        reasons = ["package_content_unverified", "no_egress_execution_unverified"]
        state = "declaration_bound"
        if package is None:
            state = "blocked"
            reasons.insert(0, "package_metadata_missing")
        else:
            package = _object(
                package,
                (
                    "digest",
                    "closure_digest",
                    "cache_digest",
                    "created_at",
                    "expires_at",
                    "identity",
                    "download_policy",
                    "evidence_digest",
                ),
            )
            for key in ("digest", "closure_digest", "cache_digest", "evidence_digest"):
                _text(package[key], DIGEST)
            created, expires = timestamp(package["created_at"]), timestamp(package["expires_at"])
            if expires <= created or created > now:
                raise EvidenceRejected("package timestamps out of order")
            if package["download_policy"] != "deny":
                state = "blocked"
                reasons.insert(0, "zero_download_policy_missing")
            if identity(package["identity"]) != ident:
                state = "blocked"
                reasons.insert(0, "package_identity_mismatch")
            if expires <= now:
                state = "blocked"
                reasons.insert(0, "package_expired")
        result.append({**row, "identity": ident, "package": package, "state": state, "reasons": reasons})
    return result


def plan_actions(document: dict[str, Any], now: dt.datetime) -> list[dict[str, Any]]:
    _object(document, ("schema", "now", "mode", "status", "actions", "state"))
    if (
        document["schema"] != "bheem.checkpoint.plan.v1"
        or document["mode"] not in {"shadow", "dispatch"}
        or document["status"] != "PLANNED"
    ):
        raise EvidenceRejected("unsupported checkpoint plan")
    observed = timestamp(document["now"])
    if observed > now:
        raise EvidenceRejected("future checkpoint plan")
    result = []
    for value in _items(document["actions"]):
        row = _object(
            value,
            ("kind", "checkpoint_id", "identity", "dispatch_ref", "reason"),
            ("attempt", "idempotency_key", "not_before", "replaces_checkpoint_id", "run_id"),
        )
        if row["kind"] not in ACTIONS or row["checkpoint_id"] != checkpoint_id(row["identity"]):
            raise EvidenceRejected("checkpoint action identity mismatch")
        for key in ("dispatch_ref", "reason"):
            _text(row[key], maximum=160)
        if "not_before" in row:
            timestamp(row["not_before"])
        for key in ("attempt", "run_id"):
            if key in row:
                _count(row[key])
        for key in ("idempotency_key", "replaces_checkpoint_id"):
            if key in row:
                _text(row[key], HEX)
        result.append(
            {
                "checkpoint_id": row["checkpoint_id"],
                "identity": identity(row["identity"]),
                "action": row["kind"],
                "reason": row["reason"],
                "observed_at": document["now"],
                "not_before": row.get("not_before"),
                "stale": (now - observed).total_seconds() > 1800,
            }
        )
    return result


def _metric(value: Any, unit: str) -> dict[str, Any]:
    row = _object(value, ("value", "unit", "quality", "scope"), ("reason",))
    if row["unit"] != unit:
        raise EvidenceRejected("metric unit mismatch")
    reason = _text(row.get("reason", ""), empty=True)
    if row["quality"] == "unavailable":
        if row["value"] is not None or not reason:
            raise EvidenceRejected("unavailable metric needs a null and reason")
        if row["scope"]:
            _text(row["scope"], SCOPE)
    else:
        if row["quality"] not in {"measured", "sampled_estimate", "allocated_share"}:
            raise EvidenceRejected("unsupported metric quality")
        _number(row["value"])
        _text(row["scope"], SCOPE)
        if row["quality"] != "measured" and not reason:
            raise EvidenceRejected("estimate needs a reason")
    return row


def workload_observation(document: dict[str, Any]) -> dict[str, Any]:
    """Validate/project resource fields. This is not Bheem's assurance validator."""
    _object(
        document,
        (
            "schema",
            "run_id",
            "identity",
            "machine",
            "cache",
            "limits",
            "controls",
            "collector",
            "timing",
            "outcome",
            "tests",
            "metrics",
            "network_boundary",
            "reasons",
        ),
    )
    if document["schema"] != "bheem.workload-run.v1":
        raise EvidenceRejected("unsupported workload schema")
    _text(document["run_id"], ID)
    raw = _object(document["identity"], RUN_IDENTITY_KEYS, ("pr_number",))
    for key in ("source_sha", "base_sha"):
        _text(raw[key], GIT)
    repository = _text(raw["repository"], maximum=193)
    if len(repository.split("/")) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,95}", part) for part in repository.split("/")
    ):
        raise EvidenceRejected("invalid workload repository identity")
    for key in RUN_IDENTITY_KEYS[3:]:
        _text(raw[key], DIGEST)
    if "pr_number" in raw:
        _count(raw["pr_number"])
    for key in ("machine_id", "surface_id", "host_class"):
        _text(_object(document["machine"], ("machine_id", "surface_id", "host_class"))[key], ID)
    if _object(document["cache"], ("state",))["state"] not in {"cold", "warm", "mixed", "unknown"}:
        raise EvidenceRejected("unsupported cache state")
    limits = _object(
        document["limits"], ("cpu_limit_cores", "memory_limit_bytes", "max_parallelism", "active_workloads")
    )
    _number(limits["cpu_limit_cores"])
    for key in ("memory_limit_bytes", "max_parallelism", "active_workloads"):
        _count(limits[key])
    controls = _object(
        document["controls"],
        ("source", "cpu_quota_cores", "cpu_unlimited", "memory_max_bytes", "memory_unlimited", "omissions"),
    )
    _text(controls["source"], SCOPE)
    quota = _number(controls["cpu_quota_cores"], True)
    if quota == 0:
        raise EvidenceRejected("observed CPU quota must be positive")
    _count(controls["memory_max_bytes"], True)
    for resource, cap in (("cpu", "cpu_quota_cores"), ("memory", "memory_max_bytes")):
        if _bool(controls[resource + "_unlimited"]) and controls[cap] is not None:
            raise EvidenceRejected("unlimited control contradicts cap")
    collector = _object(document["collector"], ("source", "version", "scope", "coverage", "omissions"))
    for key in ("source", "scope"):
        _text(collector[key], SCOPE)
    _text(collector["version"], ID)
    if collector["coverage"] not in {"partial", "complete_boundary"}:
        raise EvidenceRejected("unsupported collector coverage")
    if collector["coverage"] == "partial" and not collector["omissions"]:
        raise EvidenceRejected("partial collector needs omissions")
    for values in (controls["omissions"], collector["omissions"], document["reasons"]):
        for reason in _items([] if values is None else values, 32):
            _text(reason)
    timing = _object(
        document["timing"],
        ("started_at", "finished_at", "wall", "queue", "phases"),
        ("requested_at", "eligible_at", "dispatched_at"),
    )
    times = [
        timestamp(timing[key])
        for key in ("requested_at", "eligible_at", "dispatched_at", "started_at", "finished_at")
        if timing.get(key)
    ]
    if not timing["started_at"] or not timing["finished_at"] or times != sorted(times):
        raise EvidenceRejected("workload timestamps out of order")
    for key in ("wall", "queue"):
        _metric(timing[key], "s")
    names: set[str] = set()
    for phase in _items([] if timing["phases"] is None else timing["phases"], 16):
        _object(phase, ("name", "elapsed"))
        name = _text(phase["name"], ID)
        if name in names:
            raise EvidenceRejected("duplicate phase")
        names.add(name)
        _metric(phase["elapsed"], "s")
    outcome = _object(document["outcome"], ("status", "exit_code"))
    exit_code = outcome["exit_code"]
    if outcome["status"] not in {"passed", "failed", "cancelled", "timeout", "incomplete"}:
        raise EvidenceRejected("unsupported workload outcome")
    if exit_code is not None and (
        isinstance(exit_code, bool) or not isinstance(exit_code, int) or not -1 <= exit_code <= 255
    ):
        raise EvidenceRejected("invalid exit code")
    if (outcome["status"] == "passed" and exit_code != 0) or (
        outcome["status"] == "failed" and (exit_code is None or exit_code == 0)
    ):
        raise EvidenceRejected("outcome contradicts exit code")
    tests = _object(document["tests"], ("source", "executed", "failed", "skipped", "coverage_percent"))
    _text(tests["source"], SCOPE)
    for key in ("executed", "failed", "skipped"):
        _count(tests[key], True)
    coverage = _number(tests["coverage_percent"], True)
    if coverage is not None and coverage > 100:
        raise EvidenceRejected("invalid coverage percent")
    if (tests["executed"] is not None and tests["failed"] is not None and tests["failed"] > tests["executed"]) or (
        outcome["status"] == "passed" and tests["failed"] not in (None, 0)
    ):
        raise EvidenceRejected("test counts contradict outcome")
    metrics = _object(
        document["metrics"], ("cpu", "peak_memory", "disk_read", "disk_write", "network_received", "network_sent")
    )
    for key in metrics:
        _metric(metrics[key], "CPU-s" if key == "cpu" else "bytes")
    boundary = _object(
        document["network_boundary"], ("kind",), ("source", "version", "scope", "evidence_digest", "reason")
    )
    if boundary["kind"] == "unavailable":
        if any(boundary.get(key) for key in ("source", "version", "scope", "evidence_digest")):
            raise EvidenceRejected("unavailable boundary contains evidence")
        _text(boundary.get("reason"))
    elif boundary["kind"] in {"isolation", "counter"}:
        for key in ("source", "scope"):
            _text(boundary.get(key), SCOPE)
        _text(boundary.get("version"), ID)
        _text(boundary.get("evidence_digest"), DIGEST)
    else:
        raise EvidenceRejected("unsupported network boundary")
    for key in ("network_received", "network_sent"):
        if metrics[key]["quality"] != "unavailable" and (
            boundary["kind"] != "counter" or metrics[key]["scope"] != boundary["scope"]
        ):
            raise EvidenceRejected("traffic requires counters for the same boundary")
    return document


def assemble(
    collection: dict[str, Any],
    *,
    bindings: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    runs: list[dict[str, Any]] | None = None,
    now: dt.datetime | None = None,
    synthetic: bool = False,
) -> dict[str, Any]:
    current = now or dt.datetime.now(dt.UTC)
    rows = load_bindings(bindings, current) if bindings else []
    actions = plan_actions(plan, current) if plan else []
    observations = [dict(workload_observation(run)) for run in (runs or [])]
    seen: set[str] = set()
    for run in observations:
        if run["run_id"] in seen:
            raise EvidenceRejected("duplicate workload run ID")
        seen.add(run["run_id"])
        matches = [
            row
            for row in rows
            if all(row["identity"].get(key) == run["identity"].get(key) for key in (*RUN_IDENTITY_KEYS, "pr_number"))
        ]
        run["binding_checkpoint_id"] = matches[0]["checkpoint_id"] if len(matches) == 1 else None
    return {
        "schema": SCHEMA,
        "generated_at": current.isoformat(),
        "synthetic": synthetic,
        "collection": collection,
        "bindings": rows,
        "actions": actions,
        "runs": observations,
        "comparison": {"state": "unavailable", "reason": "no_matched_before_after_comparison_imported"},
    }


def validate_report(document: dict[str, Any]) -> dict[str, Any]:
    _walk(document)
    _object(
        document, ("schema", "generated_at", "synthetic", "collection", "bindings", "actions", "runs", "comparison")
    )
    if document["schema"] != SCHEMA:
        raise EvidenceRejected("unsupported efficiency report")
    now = timestamp(document["generated_at"])
    _bool(document["synthetic"])
    health = _object(document["collection"], COLLECTION_KEYS)
    _text(health["state"], ID)
    for key in COLLECTION_KEYS[1:3]:
        _count(health[key], True)
    _bool(health["counts_complete"])
    for key in COLLECTION_KEYS[4:10]:
        _count(health[key])
    if health["last_successful_export"] is not None:
        timestamp(health["last_successful_export"])
    indexes = _object(health["indexes"], CATALOG_NAMES)
    for state in indexes.values():
        if state not in {"readable", "missing", "malformed", "unreadable"}:
            raise EvidenceRejected("unknown catalog state")
    for source in _items(health["sources"]):
        _object(source, ("source_id", "kind", "state"))
        for key in source:
            _text(source[key], ID)
    raw_bindings = []
    for row in _items(document["bindings"]):
        _object(row, ("session_id", "worktree_id", "checkpoint_id", "identity", "package", "state", "reasons"))
        raw_bindings.append(
            {key: row[key] for key in ("session_id", "worktree_id", "checkpoint_id", "identity", "package")}
        )
    rebuilt = load_bindings(
        {"schema": BINDING_SCHEMA, "generated_at": document["generated_at"], "bindings": raw_bindings}, now
    )
    if rebuilt != document["bindings"]:
        raise EvidenceRejected("binding state differs from its evidence")
    for action in _items(document["actions"]):
        _object(action, ("checkpoint_id", "identity", "action", "reason", "observed_at", "not_before", "stale"))
        if action["action"] not in ACTIONS or action["checkpoint_id"] != checkpoint_id(action["identity"]):
            raise EvidenceRejected("action identity mismatch")
        _text(action["reason"])
        observed = timestamp(action["observed_at"])
        if observed > now or _bool(action["stale"]) != ((now - observed).total_seconds() > 1800):
            raise EvidenceRejected("action freshness differs from its timestamp")
        if action["not_before"] is not None:
            timestamp(action["not_before"])
    inputs = []
    for row in _items(document["runs"]):
        row = dict(row)
        row.pop("binding_checkpoint_id", None)
        inputs.append(row)
    rebuilt_runs = assemble(
        health,
        bindings={"schema": BINDING_SCHEMA, "generated_at": document["generated_at"], "bindings": raw_bindings},
        runs=inputs,
        now=now,
    )["runs"]
    if rebuilt_runs != document["runs"]:
        raise EvidenceRejected("run binding differs from its identity")
    comparison = _object(document["comparison"], ("state", "reason"))
    if comparison != {"state": "unavailable", "reason": "no_matched_before_after_comparison_imported"}:
        raise EvidenceRejected("unsupported comparison claim")
    return document
