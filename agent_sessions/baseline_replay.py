"""Deterministic replay selection (#25, K8).

`baseline replay select` scores archived sessions for replayability and writes a
deterministic manifest of *selected* candidates plus *near-miss* candidates with
explicit exclusion reasons. Coding sessions are excluded in v1 (decision D5) —
the archive stores transcripts, not the workspace state they ran against, so a
faithful code replay is not yet possible.

The manifest carries session references, scores, and exclusion reasons only — no
transcript excerpts — so it is safe to track in Git (see the artifacts table in
`docs/BASELINE_KNOWLEDGE_REPLAY_PLAN.md`). Excerpts live only in the gitignored
bundle produced later by `baseline replay bundle` (K10) after redaction (K9).

Selection is a pure function of the archive, so re-running with no new sessions
reproduces the manifest byte-for-byte (gate R2-dedup).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .baseline_settings import load_baseline_settings
from .config import ArchiveConfig
from .utils import archive_markdown_path, read_jsonl_dicts, slugify

DEFAULT_MANIFEST_PATH = Path("baseline/replay/manifest.jsonl")

# Replayability thresholds (issue #25 heuristics). Kept as module constants so
# tests and future calibration can reference the same numbers.
MIN_MESSAGES = 3
MAX_MESSAGES = 40
MAX_USER_TURNS = 4
MAX_TRANSCRIPT_CHARS = 60_000
MIN_FIRST_PROMPT_CHARS = 200
CODING_FENCE_THRESHOLD = 6

RUBRIC_VERSION = "replay-rubric-v1"
REPLAY_CONSTRAINTS = (
    "Re-execute the task prompt fresh. Do not read the original deliverable before producing your own.",
    "Use a different model lineage than the original run where possible (cross-lineage second opinion).",
    "Emit proposals conforming to baseline/proposals/proposal.schema.json extended with replay provenance"
    " (replay_of, replayer, rubric_version).",
    "Never auto-promote. Output is a human-reviewed proposal only.",
)
REPLAY_RUBRIC = (
    "# Replay comparison rubric\n\n"
    f"Rubric version: `{RUBRIC_VERSION}`\n\n"
    "Compare the replayed deliverable against the original along these axes, and report only"
    " generalizable lessons (not one-off nitpicks):\n\n"
    "1. Correctness deltas — did the replay get something right/wrong that the original did not?\n"
    "2. Missed requirements — requirements in the task prompt that either run failed to address.\n"
    "3. Structure/method improvements — clearer decomposition, better evidence, safer approach.\n"
    "4. Generalizable lessons — reusable guidance worth proposing into the baseline.\n"
)

USER_TURN_RE = re.compile(r"^#{1,6}\s*(?:\d+\.\s*)?user\b", re.IGNORECASE | re.MULTILINE)
ROLE_RE = re.compile(r"^#{1,6}\s*(?:\d+\.\s*)?(user|assistant|system|tool)\b", re.IGNORECASE)
TURN_HEADER_RE = re.compile(r"^#{1,6}\s*(?:\d+\.\s*)?(?:user|assistant|system|tool)\b", re.IGNORECASE | re.MULTILINE)
DIFF_HUNK_RE = re.compile(r"^(?:@@ .* @@|diff --git |\+\+\+ |--- )", re.MULTILINE)
FENCE_RE = re.compile(r"^```", re.MULTILINE)
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}", re.MULTILINE)

# Deterministic content-keyword classes for the ``--kind`` filter. First match
# in this order wins so classification is stable.
KIND_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("planning", ("plan", "design doc", "roadmap", "tracker", "milestone", "architecture")),
    ("research", ("research", "compare", "trade-off", "tradeoff", "findings", "prior art", "sources")),
    ("documentation", ("readme", "documentation", "changelog", "docs/", "guide")),
    ("writing", ("draft", "outline", "blog", "essay", "write-up", "narrative")),
    ("analysis", ("analysis", "analyze", "summarize", "summary", "evaluate", "review")),
)


@dataclass(frozen=True)
class ReplayCandidate:
    id: str
    sha256: str
    markdown_path: str
    session_id: str
    source: str
    project_slug: str
    kind: str
    messages: int
    user_turns: int
    transcript_chars: int
    score: float
    eligible: bool
    selected: bool = False
    exclusion_reasons: tuple[str, ...] = field(default_factory=tuple)


def normalized_markdown(markdown: str) -> str:
    return markdown.replace("\\", "/").strip()


def project_slug_from_metadata(metadata: dict[str, Any]) -> str:
    raw = str(metadata.get("project") or metadata.get("cwd") or "").strip()
    if not raw:
        return "unknown-project"
    from urllib.parse import unquote

    decoded = unquote(raw).replace("\\", "/").rstrip("/")
    basename = decoded.split("/")[-1] if decoded else ""
    return slugify(basename or decoded or "unknown-project")


def count_user_turns(text: str) -> int:
    return len(USER_TURN_RE.findall(text))


def first_user_prompt_chars(text: str) -> int:
    """Length of the first user turn's body (self-containedness proxy)."""
    match = USER_TURN_RE.search(text)
    if not match:
        return 0
    start = match.end()
    nxt = TURN_HEADER_RE.search(text, start)
    end = nxt.start() if nxt else len(text)
    return len(text[start:end].strip())


def looks_like_coding_session(text: str, fence_count: int) -> bool:
    if DIFF_HUNK_RE.search(text):
        return True
    return fence_count >= CODING_FENCE_THRESHOLD


def has_deliverable(text: str) -> bool:
    """A table, or a *content* heading (not a turn header) in the latter half of
    the transcript, counts as a detectable deliverable to compare a replay
    against. Turn headers like ``### 2. assistant`` are ignored so that every
    transcript does not trivially look like it has a deliverable."""
    if TABLE_SEP_RE.search(text):
        return True
    tail = text[len(text) // 2 :]
    for line in tail.splitlines():
        stripped = line.strip()
        if stripped.startswith("##") and not TURN_HEADER_RE.match(stripped):
            return True
    return False


def infer_kind(text: str, is_coding: bool) -> str:
    if is_coding:
        return "coding"
    lowered = text.lower()
    for kind, keywords in KIND_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return kind
    return "other"


def score_candidate(*, messages: int, user_turns: int, first_prompt_chars: int, deliverable: bool) -> float:
    score = 0.4
    if MIN_MESSAGES <= messages <= MAX_MESSAGES:
        score += 0.2
    if user_turns <= MAX_USER_TURNS:
        score += 0.15
    if first_prompt_chars >= MIN_FIRST_PROMPT_CHARS:
        score += 0.15
    if deliverable:
        score += 0.1
    return round(min(score, 1.0), 2)


def evaluate_record(config: ArchiveConfig, record: dict[str, Any]) -> ReplayCandidate | None:
    """Turn one archive index record into a scored replay candidate.

    Returns ``None`` for records with no markdown path at all; a missing file on
    disk is reported as an ineligible candidate (not silently dropped)."""
    markdown = normalized_markdown(str(record.get("markdown", "")))
    if not markdown:
        return None
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    sha256 = str(record.get("sha256", "")).strip()
    session_id = str(metadata.get("session_id") or metadata.get("id") or "").strip()
    source = str(record.get("source", "unknown"))
    project_slug = project_slug_from_metadata(metadata)
    messages = int(record.get("messages", 0) or 0)
    candidate_id = f"replay.{(sha256 or session_id or markdown)[:12]}"

    md_path = archive_markdown_path(config.repo_root, markdown)
    reasons: list[str] = []
    if not md_path.exists():
        return ReplayCandidate(
            id=candidate_id,
            sha256=sha256,
            markdown_path=markdown,
            session_id=session_id,
            source=source,
            project_slug=project_slug,
            kind="unknown",
            messages=messages,
            user_turns=0,
            transcript_chars=0,
            score=0.0,
            eligible=False,
            exclusion_reasons=("archive markdown file not found",),
        )

    text = md_path.read_text(encoding="utf-8", errors="replace")
    transcript_chars = len(text)
    fence_count = len(FENCE_RE.findall(text))
    user_turns = count_user_turns(text)
    first_prompt = first_user_prompt_chars(text)
    is_coding = looks_like_coding_session(text, fence_count)
    deliverable = has_deliverable(text)
    kind = infer_kind(text, is_coding)

    if is_coding:
        reasons.append("coding session excluded in v1 (D5): no workspace snapshot")
    if messages < MIN_MESSAGES:
        reasons.append(f"too few messages ({messages} < {MIN_MESSAGES})")
    if messages > MAX_MESSAGES:
        reasons.append(f"too many messages ({messages} > {MAX_MESSAGES})")
    if user_turns > MAX_USER_TURNS:
        reasons.append(f"not self-contained ({user_turns} user turns > {MAX_USER_TURNS})")
    if transcript_chars > MAX_TRANSCRIPT_CHARS:
        reasons.append(f"transcript too large ({transcript_chars} chars > {MAX_TRANSCRIPT_CHARS})")
    if first_prompt < MIN_FIRST_PROMPT_CHARS:
        reasons.append(f"first prompt too short ({first_prompt} chars < {MIN_FIRST_PROMPT_CHARS})")
    if not deliverable:
        reasons.append("no detectable deliverable (table/section) to compare against")

    eligible = not reasons
    score = score_candidate(
        messages=messages,
        user_turns=user_turns,
        first_prompt_chars=first_prompt,
        deliverable=deliverable,
    )
    return ReplayCandidate(
        id=candidate_id,
        sha256=sha256,
        markdown_path=markdown,
        session_id=session_id,
        source=source,
        project_slug=project_slug,
        kind=kind,
        messages=messages,
        user_turns=user_turns,
        transcript_chars=transcript_chars,
        score=score,
        eligible=eligible,
        exclusion_reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class ReplaySelection:
    scanned: int
    selected: tuple[ReplayCandidate, ...]
    near_misses: tuple[ReplayCandidate, ...]
    excluded_hard: int
    kind_filter: str | None


def select_replay_candidates(
    config: ArchiveConfig,
    *,
    kind: str | None = None,
    limit: int = 20,
    max_archive_records: int = 0,
    near_miss_limit: int | None = None,
) -> ReplaySelection:
    index_path = config.archive_dir / "index.jsonl"
    records = read_jsonl_dicts(index_path, label="archive/index.jsonl") if index_path.exists() else []
    if max_archive_records > 0:
        records = records[:max_archive_records]

    candidates = [candidate for record in records if (candidate := evaluate_record(config, record)) is not None]
    eligible = [c for c in candidates if c.eligible]
    if kind:
        matching = [c for c in eligible if c.kind == kind]
        mismatched = [c for c in eligible if c.kind != kind]
    else:
        matching = eligible
        mismatched = []

    # Deterministic ordering: best score first, then markdown path as tiebreak.
    matching.sort(key=lambda c: (-c.score, c.markdown_path))
    chosen = matching[: max(limit, 0)]
    overflow = matching[max(limit, 0) :]

    selected = tuple(_with_flags(c, selected=True) for c in chosen)
    near_cap = limit if near_miss_limit is None else near_miss_limit
    near_source: list[ReplayCandidate] = []
    for c in overflow:
        near_source.append(_with_reason(c, f"eligible but over selection limit ({limit})"))
    for c in mismatched:
        near_source.append(_with_reason(c, f"kind filter: `{c.kind}` != `{kind}`"))
    near_source.sort(key=lambda c: (-c.score, c.markdown_path))
    near_misses = tuple(near_source[: max(near_cap, 0)])
    excluded_hard = sum(1 for c in candidates if not c.eligible)
    return ReplaySelection(
        scanned=len(candidates),
        selected=selected,
        near_misses=near_misses,
        excluded_hard=excluded_hard,
        kind_filter=kind,
    )


def _with_flags(candidate: ReplayCandidate, *, selected: bool) -> ReplayCandidate:
    return ReplayCandidate(
        id=candidate.id,
        sha256=candidate.sha256,
        markdown_path=candidate.markdown_path,
        session_id=candidate.session_id,
        source=candidate.source,
        project_slug=candidate.project_slug,
        kind=candidate.kind,
        messages=candidate.messages,
        user_turns=candidate.user_turns,
        transcript_chars=candidate.transcript_chars,
        score=candidate.score,
        eligible=candidate.eligible,
        selected=selected,
        exclusion_reasons=candidate.exclusion_reasons,
    )


def _with_reason(candidate: ReplayCandidate, reason: str) -> ReplayCandidate:
    return ReplayCandidate(
        id=candidate.id,
        sha256=candidate.sha256,
        markdown_path=candidate.markdown_path,
        session_id=candidate.session_id,
        source=candidate.source,
        project_slug=candidate.project_slug,
        kind=candidate.kind,
        messages=candidate.messages,
        user_turns=candidate.user_turns,
        transcript_chars=candidate.transcript_chars,
        score=candidate.score,
        eligible=candidate.eligible,
        selected=False,
        exclusion_reasons=candidate.exclusion_reasons + (reason,),
    )


def candidate_to_dict(candidate: ReplayCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "sha256": candidate.sha256,
        "markdown_path": candidate.markdown_path,
        "session_id": candidate.session_id,
        "source": candidate.source,
        "project_slug": candidate.project_slug,
        "kind": candidate.kind,
        "messages": candidate.messages,
        "user_turns": candidate.user_turns,
        "transcript_chars": candidate.transcript_chars,
        "score": candidate.score,
        "eligible": candidate.eligible,
        "selected": candidate.selected,
        "exclusion_reasons": list(candidate.exclusion_reasons),
    }


def render_manifest_jsonl(selection: ReplaySelection) -> str:
    records = [*selection.selected, *selection.near_misses]
    records = sorted(records, key=lambda c: (0 if c.selected else 1, -c.score, c.markdown_path))
    lines = [json.dumps(candidate_to_dict(c), ensure_ascii=False, sort_keys=True) for c in records]
    return "\n".join(lines) + ("\n" if lines else "")


def baseline_replay_select(
    config: ArchiveConfig,
    *,
    kind: str | None = None,
    limit: int = 20,
    output: Path | None = None,
    max_archive_records: int = 0,
    dry_run: bool = False,
) -> int:
    if limit <= 0:
        raise SystemExit("--limit must be greater than 0.")
    settings = load_baseline_settings(config)
    target = output or settings.root / "replay" / "manifest.jsonl"
    if not target.is_absolute():
        target = config.repo_root / target
    selection = select_replay_candidates(
        config,
        kind=kind,
        limit=limit,
        max_archive_records=max_archive_records,
    )
    manifest = render_manifest_jsonl(selection)
    summary = _summary_line(selection)
    if dry_run:
        print(manifest, end="")
        print(summary)
        print(f"Would write {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest, encoding="utf-8", newline="\n")
    print(f"Wrote {target}")
    print(summary)
    return 0


def _summary_line(selection: ReplaySelection) -> str:
    kind_text = f" kind=`{selection.kind_filter}`" if selection.kind_filter else ""
    return (
        f"Scanned {selection.scanned} candidate(s){kind_text}: "
        f"{len(selection.selected)} selected, {len(selection.near_misses)} near-miss, "
        f"{selection.excluded_hard} hard-excluded."
    )


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_jsonl_dicts(path, label=str(path))


def selected_manifest_entries(path: Path) -> list[dict[str, Any]]:
    return [record for record in load_manifest(path) if record.get("selected") is True]


def split_turns(text: str) -> list[tuple[str, str]]:
    """Split an exported transcript into ``(role, body)`` turns by its role
    headers (``### 2. assistant`` etc.). Best-effort for this repo's export
    format; sources formatted differently yield no turns."""
    turns: list[tuple[str, str]] = []
    matches = list(TURN_HEADER_RE.finditer(text))
    for index, match in enumerate(matches):
        role_match = ROLE_RE.match(text[match.start() :])
        role = role_match.group(1).lower() if role_match else "unknown"
        line_end = text.find("\n", match.start())
        body_start = line_end + 1 if line_end != -1 else len(text)
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        turns.append((role, text[body_start:body_end].strip()))
    return turns


def extract_task_and_deliverable(text: str) -> tuple[str, str]:
    turns = split_turns(text)
    task = next((body for role, body in turns if role == "user"), "")
    deliverable = next((body for role, body in reversed(turns) if role == "assistant"), "")
    return task, deliverable


def build_replay_packet(
    entry: dict[str, Any],
    *,
    task_prompt: str,
    original_deliverable: str,
    access_tier: str,
) -> dict[str, Any]:
    return {
        "replay_of": str(entry.get("session_id") or entry.get("sha256") or entry.get("id") or ""),
        "id": str(entry.get("id", "")),
        "source": str(entry.get("source", "")),
        "project_slug": str(entry.get("project_slug", "")),
        "markdown_path": str(entry.get("markdown_path", "")),
        "kind": str(entry.get("kind", "")),
        "access_tier": access_tier,
        "rubric_version": RUBRIC_VERSION,
        "constraints": list(REPLAY_CONSTRAINTS),
        "task_prompt": task_prompt,
        "original_deliverable": original_deliverable,
    }


def baseline_replay_bundle(
    config: ArchiveConfig,
    *,
    manifest: Path | None = None,
    output_dir: Path | None = None,
    limit: int = 0,
    access_tier: str = "session-only",
    dry_run: bool = False,
) -> int:
    """Write gitignored replay packets (K10). Each selected session's task prompt
    and original deliverable are redacted (K9); a session is skipped, never
    written, if its egress content trips the fail-closed secret scanner. Every
    bundle carries its own ``redaction-report.json`` (valueless)."""
    from .baseline_redaction import redact_text, result_to_report

    settings = load_baseline_settings(config)
    manifest_path = manifest or settings.root / "replay" / "manifest.jsonl"
    if not manifest_path.is_absolute():
        manifest_path = config.repo_root / manifest_path
    if not manifest_path.exists():
        raise SystemExit(f"Replay manifest does not exist: {manifest_path}. Run `baseline replay select` first.")

    bundles_dir = output_dir or settings.root / "replay" / "bundles"
    if not bundles_dir.is_absolute():
        bundles_dir = config.repo_root / bundles_dir

    entries = selected_manifest_entries(manifest_path)
    if limit > 0:
        entries = entries[:limit]

    written: list[str] = []
    skipped: list[str] = []
    for entry in sorted(entries, key=lambda e: str(e.get("id", ""))):
        candidate_id = str(entry.get("id", "")) or "replay.unknown"
        markdown_path = str(entry.get("markdown_path", ""))
        md = archive_markdown_path(config.repo_root, markdown_path)
        text = md.read_text(encoding="utf-8", errors="replace") if md.exists() else ""
        task_raw, deliverable_raw = extract_task_and_deliverable(text)
        task_res = redact_text(task_raw)
        deliverable_res = redact_text(deliverable_raw)
        blocked = task_res.blocked or deliverable_res.blocked
        report = {
            "id": candidate_id,
            "blocked": blocked,
            "task": result_to_report(f"{candidate_id}:task", task_res),
            "deliverable": result_to_report(f"{candidate_id}:deliverable", deliverable_res),
        }
        if blocked:
            skipped.append(candidate_id)
            if not dry_run:
                _write_skip_report(bundles_dir / candidate_id, report)
            continue
        packet = build_replay_packet(
            entry,
            task_prompt=task_res.redacted_text,
            original_deliverable=deliverable_res.redacted_text,
            access_tier=access_tier,
        )
        written.append(candidate_id)
        if not dry_run:
            _write_bundle(bundles_dir / candidate_id, packet, report)

    summary = (
        f"Replay bundle: {len(written)} written, {len(skipped)} skipped (redaction-blocked). "
        f"Output dir (gitignored): {bundles_dir}"
    )
    print(summary)
    return 0


def _write_bundle(bundle_dir: Path, packet: dict[str, Any], report: dict[str, Any]) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "packet.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (bundle_dir / "rubric.md").write_text(REPLAY_RUBRIC, encoding="utf-8", newline="\n")
    (bundle_dir / "redaction-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def _write_skip_report(bundle_dir: Path, report: dict[str, Any]) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "redaction-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def baseline_replay_redact(
    config: ArchiveConfig,
    *,
    manifest: Path | None = None,
    output: Path | None = None,
    limit: int = 0,
    dry_run: bool = False,
) -> int:
    """Redaction preflight (K9): scan the selected sessions and write a
    fail-closed redaction report. Returns non-zero when any candidate contains a
    high-confidence secret, so the egress gate blocks before any bundle exists.
    No transcript content is written — only counts, placeholder ids, and blocked
    reasons land in the report."""
    from .baseline_redaction import build_preflight_report, preflight_to_dict, write_preflight_report

    settings = load_baseline_settings(config)
    manifest_path = manifest or settings.root / "replay" / "manifest.jsonl"
    if not manifest_path.is_absolute():
        manifest_path = config.repo_root / manifest_path
    if not manifest_path.exists():
        raise SystemExit(f"Replay manifest does not exist: {manifest_path}. Run `baseline replay select` first.")

    entries = selected_manifest_entries(manifest_path)
    if limit > 0:
        entries = entries[:limit]
    items: list[tuple[str, str]] = []
    for entry in entries:
        markdown_path = str(entry.get("markdown_path", ""))
        md = archive_markdown_path(config.repo_root, markdown_path)
        text = md.read_text(encoding="utf-8", errors="replace") if md.exists() else ""
        items.append((str(entry.get("id") or markdown_path), text))

    preflight = build_preflight_report(items, generated_at=dt.date.today().isoformat())
    report_path = output or settings.root / "replay" / "bundles" / "redaction-preflight.json"
    if not report_path.is_absolute():
        report_path = config.repo_root / report_path
    summary = (
        f"Redaction preflight ({preflight.scanner_version}): {preflight.total} candidate(s), "
        f"{preflight.blocked} blocked, {preflight.allowed} allowed."
    )
    if dry_run:
        print(json.dumps(preflight_to_dict(preflight), indent=2, ensure_ascii=False, sort_keys=True))
        print(summary)
    else:
        write_preflight_report(report_path, preflight)
        print(f"Wrote {report_path}")
        print(summary)
    return 1 if preflight.blocked else 0
