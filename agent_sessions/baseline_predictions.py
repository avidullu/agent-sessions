"""Keyword signal scanning and deterministic prediction generation."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from .baseline_settings import BASELINE_CONFIG
from .baseline_types import BaselineSettings, Prediction, TextSignal, confidence
from .config import ArchiveConfig, read_toml
from .utils import active_agent_count, archive_markdown_path, dormant_agents, most_recent_first

KEYWORD_GROUPS = {
    "repo-governance": (
        "pull request",
        "pr",
        "merge",
        "approval",
        "direct push",
        "branch",
        "git add",
        "git pull --ff-only",
        "origin/main",
    ),
    "regression-frameworks": (
        "pytest",
        "ruff",
        "mypy",
        "coverage",
        "test suite",
        "ci",
        "smoke",
        "regression",
    ),
    "architecture-decisions": ("architecture", "adr", "trade-off", "pivot", "boundary", "decision"),
    "docs-freshness": ("handoff", "readme", "roadmap", "docs", "documentation", "runbook"),
    "checkpointing": ("resume", "checkpoint", "session handoff", "start here", "ramp-up"),
    "metacognition": ("pattern", "memory", "baseline", "salient", "guardrail", "calibrate", "prediction"),
    "tracked-project-docs": (
        "project_doc_template",
        "tracked project doc",
        "progress tracker",
        "definition of done",
        "decisions locked",
        "one small pr per row",
        "§7",
    ),
}

PR_ONLY_REPO_WRITES_TEXT = (
    "Agents must not push directly to durable/shared repos. They should branch from the remote base, stage "
    "explicit paths, open a PR, and merge only after explicit approval or a scoped umbrella approval. Scoped "
    "approval is limited to the named project, PR set, task, and time/context in which it was granted; it must "
    "not be reused for adjacent work, self-authored PRs, or later PRs without renewed confirmation."
)


def project_signal_counts(settings: BaselineSettings, records: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        haystack = " ".join(
            [
                str(record.get("source_file", "")),
                str(record.get("markdown", "")),
                json.dumps(record.get("metadata", {}), ensure_ascii=False),
            ]
        ).lower()
        for pilot in settings.pilots:
            names = (pilot.slug, *pilot.aliases)
            if any(name.lower() in haystack for name in names):
                counts[pilot.slug] += 1
    return counts


def scan_text_signals(
    config: ArchiveConfig, records: list[dict[str, Any]], max_sessions: int
) -> dict[str, list[TextSignal]]:
    # Scan most-recent-first so keyword signals reflect current activity,
    # not the oldest sessions in an append-only index.
    ordered = most_recent_first(records)
    selected = ordered if max_sessions == 0 else ordered[:max_sessions]
    grouped: dict[str, list[TextSignal]] = {key: [] for key in KEYWORD_GROUPS}
    for record in selected:
        markdown_path = archive_markdown_path(config.repo_root, str(record.get("markdown", "")))
        if not markdown_path.exists():
            continue
        text = markdown_path.read_text(encoding="utf-8", errors="replace").lower()
        for group, keywords in KEYWORD_GROUPS.items():
            count = keyword_hits(text, keywords)
            if count:
                grouped[group].append(
                    TextSignal(
                        source=str(record.get("source", "")),
                        markdown=str(record.get("markdown", "")),
                        count=count,
                    )
                )
    return {group: sorted(signals, key=lambda signal: signal.count, reverse=True) for group, signals in grouped.items()}


def keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    count = 0
    for keyword in keywords:
        escaped = re.escape(keyword.lower())
        if re.fullmatch(r"[a-z0-9_]+", keyword.lower()):
            pattern = rf"\b{escaped}\b"
        else:
            pattern = escaped
        count += len(re.findall(pattern, text))
    return count


def build_predictions(
    settings: BaselineSettings,
    source_counts: Counter[str],
    kind_counts: Counter[str],
    project_hits: Counter[str],
    text_signals: dict[str, list[TextSignal]],
) -> list[Prediction]:
    total_records = sum(source_counts.values())
    active_sources = active_agent_count(source_counts)
    dormant = dormant_agents(source_counts)
    agent_names = " + ".join(f"{name}={count:.0f}" for name, count in source_counts.most_common(6))
    # Dormant agents reduce the multi-agent confidence — they indicate
    # the user may have stopped using certain agents.
    dormant_penalty = len(dormant) * 0.04
    predictions = [
        Prediction(
            id="profile.multi-agent-builder",
            title="Multi-Agent Builder",
            scope="user-profile",
            risk="low",
            category="metacognition",
            confidence=confidence(
                0.46 + active_sources * 0.06 + math.log10(max(total_records, 1)) * 0.08 - dormant_penalty
            ),
            status="proposed",
            evidence=[
                f"{total_records:.0f} recency-weighted sessions across {active_sources} active canonical agents.",
                f"Agent mix (weighted): {agent_names}",
                *([f"Dormant agents: {', '.join(dormant)}"] if dormant else []),
            ],
            text=(
                "The user appears to be a heavy multi-agent builder who uses several local coding agents as part of "
                "an active engineering workflow rather than as an occasional chat-only assistant."
            ),
        ),
        Prediction(
            id="profile.local-first-private-compute",
            title="Local-First Private Compute Preference",
            scope="user-profile",
            risk="low",
            category="metacognition",
            confidence=confidence(
                0.55 + bool(source_counts.get("grok")) * 0.12 + bool(source_counts.get("codex")) * 0.08
            ),
            status="proposed",
            evidence=[
                "Windows and WSL local stores are first-class archive sources.",
                "All agents (Claude, Codex, DeepSeek, Gemini, Grok) read from local disk paths.",
            ],
            text=(
                "The user strongly prefers owned/local CPU, RAM, and disk as the default source of truth, while still "
                "allowing explicit, bounded access to external services when useful."
            ),
        ),
        Prediction(
            id="profile.business-productivity-engineer",
            title="Business/Productivity-Oriented Engineer",
            scope="user-profile",
            risk="medium",
            category="metacognition",
            confidence=confidence(0.43 + min(sum(project_hits.values()), 100) / 500),
            status="proposed",
            evidence=project_evidence(project_hits),
            text=(
                "The user looks like a builder who blends software engineering, product/business workflows, and agent "
                "automation to improve productivity across several durable projects."
            ),
        ),
        Prediction(
            id="guardrail.pr-only-repo-writes",
            title="PR-Only Repo Writes",
            scope="global",
            risk="high",
            category="repo-governance",
            confidence=signal_confidence(text_signals, "repo-governance", base=0.68),
            status="proposed",
            evidence=signal_evidence(text_signals, "repo-governance"),
            text=PR_ONLY_REPO_WRITES_TEXT,
        ),
        Prediction(
            id="guardrail.verified-regression-gates",
            title="Verified Regression Gates",
            scope="global",
            risk="high",
            category="regression-frameworks",
            confidence=signal_confidence(text_signals, "regression-frameworks", base=0.58),
            status="proposed",
            evidence=signal_evidence(text_signals, "regression-frameworks"),
            text=(
                "Agents should discover and run the repo's real test, lint, type, coverage, and smoke gates before "
                "claiming a change is ready, and clearly state anything that could not be verified."
            ),
        ),
        Prediction(
            id="guardrail.handoff-and-resume",
            title="Handoff And Resume Discipline",
            scope="global",
            risk="medium",
            category="checkpointing",
            confidence=signal_confidence(text_signals, "checkpointing", base=0.52),
            status="proposed",
            evidence=signal_evidence(text_signals, "checkpointing"),
            text=(
                "Projects should maintain a short session handoff or start-here file so future agents can resume from "
                "real state instead of replaying old conversation."
            ),
        ),
        Prediction(
            id="guardrail.tracked-project-docs",
            title="Tracked Project Docs For Substantial Work",
            scope="global",
            risk="medium",
            category="docs",
            confidence=tracked_project_doc_confidence(text_signals, settings),
            status="proposed",
            evidence=tracked_project_doc_evidence(text_signals, settings),
            text=(
                "Substantial design or multi-PR project work should use a tracked project doc following "
                "`docs/PROJECT_DOC_TEMPLATE.md`: status header, decisions locked, §7 progress tracker with one small "
                "PR per row, definition of done, then archive on completion. Precedent: `badminton-highlight-indexer`."
            ),
        ),
        Prediction(
            id="harness.predict-then-calibrate",
            title="Predict Then Calibrate",
            scope="global",
            risk="medium",
            category="metacognition",
            confidence=signal_confidence(text_signals, "metacognition", base=0.5),
            status="proposed",
            evidence=signal_evidence(text_signals, "metacognition"),
            text=(
                "The baseline system should regularly make explicit predictions about user/project patterns, ask for "
                "calibration feedback, and adjust confidence or wording based on accepted, edited, or rejected guesses."
            ),
        ),
    ]
    return predictions


def signal_confidence(text_signals: dict[str, list[TextSignal]], group: str, base: float) -> float:
    total = sum(signal.count for signal in text_signals.get(group, []))
    return confidence(base + min(total, 250) / 1000)


def project_evidence(project_hits: Counter[str]) -> list[str]:
    if not project_hits:
        return ["No configured pilot project names were detected in the archive index yet."]
    return [f"{slug}: {count} archive records" for slug, count in project_hits.most_common()]


def signal_evidence(text_signals: dict[str, list[TextSignal]], group: str) -> list[str]:
    signals = text_signals.get(group, [])
    if not signals:
        return [f"No `{group}` text signals found in scanned Markdown sessions yet."]
    evidence = [f"{len(signals)} scanned sessions contain `{group}` signals."]
    for signal in signals[:4]:
        markdown = signal.markdown.replace("\\", "/")
        evidence.append(f"{markdown} ({signal.count} keyword hits)")
    return evidence


def tracked_project_doc_confidence(
    text_signals: dict[str, list[TextSignal]],
    settings: BaselineSettings,
) -> float:
    conf = signal_confidence(text_signals, "tracked-project-docs", base=0.55)
    path = settings.root.parent / BASELINE_CONFIG
    data = read_toml(path) if path.exists() else {}
    for anchor in data.get("calibration_anchors", []):
        if anchor.get("kind") != "tracked-project-doc":
            continue
        hits = int(anchor.get("archive_hits") or 0)
        if hits:
            conf = confidence(conf + min(hits, 500) / 800)
    return conf


def tracked_project_doc_evidence(
    text_signals: dict[str, list[TextSignal]],
    settings: BaselineSettings,
) -> list[str]:
    evidence = signal_evidence(text_signals, "tracked-project-docs")
    path = settings.root.parent / BASELINE_CONFIG
    data = read_toml(path) if path.exists() else {}
    for anchor in data.get("calibration_anchors", []):
        if anchor.get("kind") != "tracked-project-doc":
            continue
        repo = anchor.get("source_repo", "unknown")
        path = anchor.get("source_path", "")
        hits = anchor.get("archive_hits")
        hit_note = f"{hits} archive sessions mention `{anchor.get('archive_signal', '')}`" if hits else ""
        evidence.append(f"Calibration anchor: `{repo}/{path}` ({hit_note})".strip())
    return evidence
