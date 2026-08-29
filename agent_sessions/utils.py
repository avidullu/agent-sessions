"""Small utility functions shared across archive modules."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Source canonicalization — maps per-machine source names and record ``kind``
# values to a stable whitelist of canonical agent names.  The original
# ``source`` field (e.g. ``claude-wsl-ubuntu``) is preserved in every record;
# canonicalization is applied at aggregation time so ``claude-windows`` and
# ``claude-wsl-ubuntu`` both count toward the same ``claude`` bucket.
# ---------------------------------------------------------------------------

# Map record ``kind`` values → canonical agent slug.
_KIND_TO_CANONICAL: dict[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "deepseek_request_dump": "deepseek",
    "gemini_antigravity": "gemini",
    "grok": "grok",
}


def canonical_agent(record: dict[str, Any]) -> str:
    """Return the canonical agent slug for an archive index record.

    Derives the agent from the record's ``kind`` field using a whitelist
    mapping.  Falls back to the ``source`` field, then ``"unknown"``.

    >>> canonical_agent({"kind": "claude", "source": "claude-windows"})
    'claude'
    >>> canonical_agent({"kind": "deepseek_request_dump", "source": "deepseek-vscode-wsl-ubuntu"})
    'deepseek'
    """
    kind = str(record.get("kind", "")).strip().lower()
    if kind == "copilot_chat":
        metadata = record.get("metadata")
        if isinstance(metadata, dict):
            provider = str(metadata.get("model_provider", "")).strip().lower()
            if provider:
                return "copilot" if provider in {"github", "github-copilot"} else provider
        return "copilot"
    if kind in _KIND_TO_CANONICAL:
        return _KIND_TO_CANONICAL[kind]
    source = str(record.get("source", "")).strip()
    return source or "unknown"


def canonical_agent_counts(records: list[dict[str, Any]]) -> Counter[str]:
    """Return ``Counter`` of canonical agent slugs from archive records.

    Unlike raw ``source`` counts, this merges per-machine variants
    (``claude-windows`` + ``claude-wsl-ubuntu`` → ``claude``).
    """
    return Counter(canonical_agent(record) for record in records)


# ---------------------------------------------------------------------------
# Recency / freshness weighting — sessions older than a threshold are
# down-weighted so predictions favour recent activity over stale archives.
# ---------------------------------------------------------------------------

#: Days after which a session begins to decay.
RECENCY_DECAY_DAYS: int = 90

#: Decay half-life in days (weight halves every 30 days beyond the threshold).
RECENCY_HALF_LIFE_DAYS: int = 30

#: Agents with weighted count below this are considered dormant.
RECENCY_DORMANT_THRESHOLD: float = 0.05


def session_age_days(record: dict[str, Any], *, now: dt.datetime | None = None) -> int:
    """Days since the session's ``mtime`` (or 0 if unavailable)."""
    mtime = record.get("mtime")
    if mtime is None:
        return 0
    session_dt = dt.datetime.fromtimestamp(float(mtime), tz=dt.UTC)
    ref = now or dt.datetime.now(dt.UTC)
    return max(0, (ref - session_dt).days)


def session_recency_weight(record: dict[str, Any], *, now: dt.datetime | None = None) -> float:
    """Weight for a single session based on age.

    * ≤ RECENCY_DECAY_DAYS old  → weight = 1.0
    * Beyond that, exponential decay with half-life RECENCY_HALF_LIFE_DAYS.
    """
    age = session_age_days(record, now=now)
    if age <= RECENCY_DECAY_DAYS:
        return 1.0
    return 0.5 ** ((age - RECENCY_DECAY_DAYS) / RECENCY_HALF_LIFE_DAYS)


def agent_recency_weights(records: list[dict[str, Any]], *, now: dt.datetime | None = None) -> Counter[str]:
    """Per-canonical-agent weighted count, summed from individual session weights.

    An agent used yesterday with 1,000 sessions gets weight ≈ 1,000.
    An agent last used 120 days ago with 4 sessions gets weight ≈ 2.

    Returns a Counter with float values (mypy stubs type Counter values as int,
    but Python allows float at runtime — the :func:`active_agent_count` and
    :func:`dormant_agents` helpers work correctly with fractional weights).
    """
    weighted: Counter[str] = Counter()
    for record in records:
        agent = canonical_agent(record)
        weight = session_recency_weight(record, now=now)
        weighted[agent] = weighted.get(agent, 0.0) + weight  # type: ignore[assignment]
    return weighted


def active_agent_count(weighted: Counter[str]) -> int:
    """Number of agents whose weighted count exceeds the dormant threshold."""
    return sum(1 for w in weighted.values() if w >= RECENCY_DORMANT_THRESHOLD)


def dormant_agents(weighted: Counter[str]) -> list[str]:
    """Agents below the dormant threshold (likely unused for a long time)."""
    return sorted(agent for agent, w in weighted.items() if 0 < w < RECENCY_DORMANT_THRESHOLD)


def most_recent_first(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return records sorted by ``mtime`` descending (newest first).

    Falls back to original order when ``mtime`` is unavailable.
    """

    def _sort_key(record: dict[str, Any]) -> float:
        mtime = record.get("mtime")
        return -float(mtime) if mtime is not None else 0.0

    return sorted(records, key=_sort_key)


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def read_jsonl_dicts(path: Path, *, label: str | None = None) -> list[dict[str, Any]]:
    """Read a JSONL file into dicts, warning on (and skipping) malformed lines.

    The single tolerant reader shared by every JSONL consumer so one corrupt
    line degrades to a warning instead of a raw ``JSONDecodeError`` traceback in
    one place and a silent skip in another.
    """
    tag = label or str(path)
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"warning: skipping malformed JSON at {tag}:{lineno}: {exc}", file=sys.stderr)
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records


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


def session_id_from_name(path: Path) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path.name, re.I)
    return match.group(1) if match else path.stem


def archive_markdown_path(repo_root: Path, markdown: str) -> Path:
    """Resolve an archive markdown path from index.jsonl (may use Windows separators)."""
    normalized = markdown.replace("\\", "/")
    return repo_root / normalized


def slugify(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^\w.\- ]+", "-", value, flags=re.ASCII)
    value = re.sub(r"\s+", "-", value.strip())
    value = value.strip(".-_")
    return (value[:max_len].strip(".-_") or "session").lower()
