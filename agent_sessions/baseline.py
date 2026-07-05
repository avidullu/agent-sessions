"""Engineering baseline scaffold and suggestion generation."""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .config import ArchiveConfig, read_toml, repo_path


BASELINE_CONFIG = Path("config/baseline.toml")
BASELINE_ROOT = Path("baseline")


@dataclass(frozen=True)
class Pilot:
    slug: str
    kind: str
    aliases: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class BaselineSettings:
    root: Path
    candidates_dir: Path
    metacognition_dir: Path
    ledger_path: Path
    feedback_example: Path
    pilots: tuple[Pilot, ...]


@dataclass
class Prediction:
    id: str
    title: str
    scope: str
    risk: str
    category: str
    confidence: float
    status: str
    evidence: list[str]
    text: str
    feedback: str = "none"


@dataclass(frozen=True)
class TextSignal:
    source: str
    markdown: str
    count: int


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
}


def baseline_scaffold(config: ArchiveConfig, dry_run: bool = False) -> int:
    settings = load_baseline_settings(config)
    files = baseline_files(settings)
    for path, content in files.items():
        if dry_run:
            print(f"Would ensure {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Baseline scaffold {'checked' if dry_run else 'ready'} at {settings.root}.")
    return 0


def baseline_suggest(
    config: ArchiveConfig,
    output: Path | None = None,
    max_sessions: int = 500,
    feedback: Path | None = None,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    index_records = load_index_records(config)
    feedback_map = load_feedback(config, feedback)
    source_counts = Counter(str(record.get("source", "")) for record in index_records)
    kind_counts = Counter(str(record.get("kind", "")) for record in index_records)
    project_hits = project_signal_counts(settings, index_records)
    text_signals = scan_text_signals(config, index_records, max_sessions=max_sessions)
    predictions = build_predictions(
        source_counts=source_counts,
        kind_counts=kind_counts,
        project_hits=project_hits,
        text_signals=text_signals,
    )
    predictions = [apply_feedback(prediction, feedback_map) for prediction in predictions]
    markdown = render_candidate_report(
        settings=settings,
        index_records=index_records,
        source_counts=source_counts,
        kind_counts=kind_counts,
        project_hits=project_hits,
        text_signals=text_signals,
        predictions=predictions,
        max_sessions=max_sessions,
        feedback_path=feedback,
    )
    target = output or settings.candidates_dir / f"{dt.date.today().isoformat()}-extraction.md"
    if not target.is_absolute():
        target = config.repo_root / target
    if dry_run:
        print(markdown)
        print(f"Would write {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    if is_relative_to(target, settings.candidates_dir):
        write_prediction_artifacts(
            settings=settings,
            candidate_path=target,
            predictions=predictions,
            source_counts=source_counts,
            kind_counts=kind_counts,
            project_hits=project_hits,
            scanned_sessions=len(index_records) if max_sessions == 0 else min(max_sessions, len(index_records)),
        )
    print(f"Wrote {target}")
    return 0


def baseline_calibrate(
    config: ArchiveConfig,
    feedback: Path,
    predictions: Path | None = None,
    output: Path | None = None,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    feedback_map = load_feedback(config, feedback)
    prediction_path = resolve_prediction_sidecar(settings, predictions)
    prediction_data = json.loads(prediction_path.read_text(encoding="utf-8"))
    summary = render_calibration_summary(prediction_data, feedback_map, feedback, prediction_path)
    target = output or settings.metacognition_dir / "calibration-summary.md"
    if not target.is_absolute():
        target = config.repo_root / target
    if dry_run:
        print(summary)
        print(f"Would write {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary, encoding="utf-8", newline="\n")
    print(f"Wrote {target}")
    return 0


def load_baseline_settings(config: ArchiveConfig) -> BaselineSettings:
    path = config.repo_root / BASELINE_CONFIG
    data = read_toml(path) if path.exists() else {}
    baseline = data.get("baseline", {})
    root = repo_path(config.repo_root, baseline.get("root", str(BASELINE_ROOT)))
    candidates_dir = repo_path(config.repo_root, baseline.get("candidates_dir", str(BASELINE_ROOT / "candidates")))
    metacognition_dir = repo_path(config.repo_root, baseline.get("metacognition_dir", str(BASELINE_ROOT / "metacognition")))
    ledger_path = repo_path(
        config.repo_root,
        baseline.get("ledger_path", str(BASELINE_ROOT / "metacognition" / "prediction-ledger.jsonl")),
    )
    feedback_example = repo_path(
        config.repo_root,
        baseline.get("feedback_example", str(BASELINE_ROOT / "calibration" / "feedback.example.toml")),
    )
    pilots = tuple(
        Pilot(
            slug=item["slug"],
            kind=item.get("kind", "repo"),
            aliases=tuple(item.get("aliases", [])),
            notes=item.get("notes", ""),
        )
        for item in data.get("pilots", [])
    )
    return BaselineSettings(
        root=root,
        candidates_dir=candidates_dir,
        metacognition_dir=metacognition_dir,
        ledger_path=ledger_path,
        feedback_example=feedback_example,
        pilots=pilots,
    )


def baseline_files(settings: BaselineSettings) -> dict[Path, str]:
    files = {
        settings.root / "README.md": baseline_readme(),
        settings.root / "candidates" / "README.md": candidates_readme(),
        settings.root / "global" / "engineering-guardrails.md": "# Engineering Guardrails\n\nPromoted guidance will land here.\n",
        settings.root / "global" / "repo-workflows.md": "# Repo Workflows\n\nPromoted repo workflow guidance will land here.\n",
        settings.root / "global" / "regression-frameworks.md": "# Regression Frameworks\n\nPromoted testing guidance will land here.\n",
        settings.root / "global" / "prompt-patterns.md": "# Prompt Patterns\n\nPromoted prompt guidance will land here.\n",
        settings.root / "agents" / "codex" / "README.md": agent_readme("Codex", "AGENTS.generated.md"),
        settings.root / "agents" / "claude" / "README.md": agent_readme("Claude", "CLAUDE.generated.md"),
        settings.root / "agents" / "vscode" / "README.md": agent_readme("VS Code", "copilot-instructions.generated.md"),
        settings.metacognition_dir / "README.md": metacognition_readme(),
        settings.feedback_example: feedback_example(),
    }
    for pilot in settings.pilots:
        files[settings.root / "projects" / pilot.slug / "README.md"] = project_readme(pilot.slug)
    return files


def baseline_readme() -> str:
    return """# Engineering Baseline

This directory holds reviewed engineering guardrails, project memory, and
agent-specific generated views derived from archived sessions and repo evidence.

Candidate files are suggestions. Promoted files are reviewed baseline guidance.
Generated agent files should stay separate from hand-written project instruction
files until their output proves useful.
"""


def candidates_readme() -> str:
    return """# Baseline Candidates

Candidate files are generated suggestions with provenance, confidence, risk, and
promotion checkboxes. Review these in PRs before promoting anything into the
global or project baseline.
"""


def agent_readme(agent_name: str, generated_name: str) -> str:
    return f"""# {agent_name} Baseline View

Generated {agent_name} instructions will land in `{generated_name}` later. Keep
this separate from hand-written project instructions until the publisher is
trusted.
"""


def project_readme(slug: str) -> str:
    return f"""# {slug}

Project-specific promoted baseline notes for `{slug}` will land here.
"""


def feedback_example() -> str:
    return """# Copy to feedback.toml and mark predictions after reviewing a candidate file.

[feedback."profile.multi-agent-builder"]
verdict = "accept"
note = "This matches the user's actual working style."

[feedback."profile.local-first-private-compute"]
verdict = "edit"
note = "Keep the local-first point, but mention that cloud APIs are acceptable when explicitly authorized."

[feedback."profile.business-productivity-engineer"]
verdict = "reject"
note = "Example of a rejected hypothesis."
"""


def metacognition_readme() -> str:
    return """# Metacognition

This folder holds machine-readable prediction history and calibration summaries.
The loop is: generate predictions from local evidence, collect feedback, compare
error, and make the next candidate report sharper.
"""


def load_index_records(config: ArchiveConfig) -> list[dict[str, Any]]:
    index_path = config.archive_dir / "index.jsonl"
    if not index_path.exists():
        raise SystemExit("archive/index.jsonl does not exist. Run export first.")
    records: list[dict[str, Any]] = []
    with index_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_feedback(config: ArchiveConfig, feedback: Path | None) -> dict[str, dict[str, str]]:
    if feedback is None:
        default = config.repo_root / "baseline" / "calibration" / "feedback.toml"
        feedback = default if default.exists() else None
    if feedback is None:
        return {}
    if not feedback.is_absolute():
        feedback = config.repo_root / feedback
    if not feedback.exists():
        raise SystemExit(f"Feedback file does not exist: {feedback}")
    data = read_toml(feedback)
    raw = data.get("feedback", {})
    return {str(key): dict(value) for key, value in raw.items() if isinstance(value, dict)}


def apply_feedback(prediction: Prediction, feedback_map: dict[str, dict[str, str]]) -> Prediction:
    item = feedback_map.get(prediction.id)
    if not item:
        return prediction
    verdict = str(item.get("verdict", "")).strip().lower()
    note = str(item.get("note", "")).strip()
    if verdict == "accept":
        prediction.status = "accepted-feedback"
        prediction.confidence = min(0.99, prediction.confidence + 0.08)
    elif verdict == "reject":
        prediction.status = "rejected-feedback"
        prediction.confidence = max(0.01, prediction.confidence - 0.35)
    elif verdict == "edit":
        prediction.status = "edit-requested"
        prediction.confidence = max(0.01, prediction.confidence - 0.08)
    prediction.feedback = f"{verdict}: {note}" if note else verdict or "present"
    return prediction


def write_prediction_artifacts(
    settings: BaselineSettings,
    candidate_path: Path,
    predictions: list[Prediction],
    source_counts: Counter[str],
    kind_counts: Counter[str],
    project_hits: Counter[str],
    scanned_sessions: int,
) -> None:
    run_id = candidate_path.stem
    payload = {
        "run_id": run_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "candidate": str(candidate_path.relative_to(settings.root.parent)).replace("\\", "/"),
        "scanned_sessions": scanned_sessions,
        "source_counts": dict(source_counts),
        "kind_counts": dict(kind_counts),
        "project_hits": dict(project_hits),
        "predictions": [prediction_to_dict(prediction) for prediction in predictions],
    }
    sidecar = candidate_path.with_suffix(".predictions.json")
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    upsert_ledger(settings.ledger_path, run_id, cast(list[dict[str, Any]], payload["predictions"]))


def prediction_to_dict(prediction: Prediction) -> dict[str, Any]:
    return {
        "id": prediction.id,
        "title": prediction.title,
        "scope": prediction.scope,
        "risk": prediction.risk,
        "category": prediction.category,
        "confidence": round(prediction.confidence, 4),
        "status": prediction.status,
        "feedback": prediction.feedback,
        "evidence": prediction.evidence,
        "text": prediction.text,
    }


def upsert_ledger(ledger_path: Path, run_id: str, predictions: list[dict[str, Any]]) -> None:
    existing: list[dict[str, Any]] = []
    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("run_id") != run_id:
                    existing.append(record)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in existing:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        recorded_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for prediction in predictions:
            record = {"run_id": run_id, "recorded_at": recorded_at, **prediction}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def resolve_prediction_sidecar(settings: BaselineSettings, predictions: Path | None) -> Path:
    if predictions is not None:
        if not predictions.is_absolute():
            predictions = settings.root.parent / predictions
        if not predictions.exists():
            raise SystemExit(f"Prediction sidecar does not exist: {predictions}")
        return predictions
    sidecars = sorted(settings.candidates_dir.glob("*.predictions.json"), key=lambda path: path.stat().st_mtime)
    if not sidecars:
        raise SystemExit("No prediction sidecar found. Run `baseline suggest` first.")
    return sidecars[-1]


def render_calibration_summary(
    prediction_data: dict[str, Any],
    feedback_map: dict[str, dict[str, str]],
    feedback_path: Path,
    prediction_path: Path,
) -> str:
    predictions = prediction_data.get("predictions", [])
    accepted: list[str] = []
    edited: list[str] = []
    rejected: list[str] = []
    missing: list[str] = []
    for prediction in predictions:
        prediction_id = prediction.get("id", "")
        feedback = feedback_map.get(prediction_id)
        if not feedback:
            missing.append(prediction_id)
            continue
        verdict = str(feedback.get("verdict", "")).strip().lower()
        if verdict == "accept":
            accepted.append(prediction_id)
        elif verdict == "edit":
            edited.append(prediction_id)
        elif verdict == "reject":
            rejected.append(prediction_id)
    lines = [
        f"# Calibration Summary ({dt.date.today().isoformat()})",
        "",
        f"- Prediction run: `{prediction_data.get('run_id', prediction_path.stem)}`",
        f"- Prediction sidecar: `{prediction_path}`",
        f"- Feedback file: `{feedback_path}`",
        f"- Predictions reviewed: `{len(predictions)}`",
        f"- Accepted: `{len(accepted)}`",
        f"- Edited: `{len(edited)}`",
        f"- Rejected: `{len(rejected)}`",
        f"- Awaiting feedback: `{len(missing)}`",
        "",
        "## Accepted",
        "",
        *render_id_list(accepted),
        "",
        "## Edit Requested",
        "",
        *render_id_list(edited),
        "",
        "## Rejected",
        "",
        *render_id_list(rejected),
        "",
        "## Awaiting Feedback",
        "",
        *render_id_list(missing),
        "",
        "## Next Correction",
        "",
        "Use accepted predictions as stronger priors, rewrite edited predictions before promotion, and suppress",
        "or reframe rejected predictions in the next candidate report.",
    ]
    return "\n".join(lines) + "\n"


def render_id_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- `{value}`" for value in values]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


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


def scan_text_signals(config: ArchiveConfig, records: list[dict[str, Any]], max_sessions: int) -> dict[str, list[TextSignal]]:
    selected = records if max_sessions == 0 else records[:max_sessions]
    grouped: dict[str, list[TextSignal]] = {key: [] for key in KEYWORD_GROUPS}
    for record in selected:
        markdown_path = config.repo_root / str(record.get("markdown", ""))
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
    source_counts: Counter[str],
    kind_counts: Counter[str],
    project_hits: Counter[str],
    text_signals: dict[str, list[TextSignal]],
) -> list[Prediction]:
    total_records = sum(source_counts.values())
    active_sources = sum(1 for count in source_counts.values() if count)
    predictions = [
        Prediction(
            id="profile.multi-agent-builder",
            title="Multi-Agent Builder",
            scope="user-profile",
            risk="low",
            category="metacognition",
            confidence=confidence(0.46 + active_sources * 0.06 + math.log10(max(total_records, 1)) * 0.08),
            status="proposed",
            evidence=[
                f"{total_records} archived session files across {active_sources} configured sources.",
                "Active source mix: " + ", ".join(f"{name}={count}" for name, count in source_counts.most_common(6)),
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
            confidence=confidence(0.55 + bool(source_counts.get("grok-wsl-ubuntu")) * 0.12 + bool(kind_counts.get("codex")) * 0.08),
            status="proposed",
            evidence=[
                "Windows and WSL local stores are first-class archive sources.",
                "Grok, Claude, Codex, DeepSeek, and Gemini sources are read from local disk paths.",
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
            text=(
                "Agents must not push directly to durable/shared repos. They should branch from the remote base, stage "
                "explicit paths, open a PR, and merge only after explicit approval or a scoped umbrella approval."
            ),
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


def confidence(value: float) -> float:
    return max(0.01, min(0.99, value))


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


def render_candidate_report(
    settings: BaselineSettings,
    index_records: list[dict[str, Any]],
    source_counts: Counter[str],
    kind_counts: Counter[str],
    project_hits: Counter[str],
    text_signals: dict[str, list[TextSignal]],
    predictions: list[Prediction],
    max_sessions: int,
    feedback_path: Path | None,
) -> str:
    scanned_count = len(index_records) if max_sessions == 0 else min(max_sessions, len(index_records))
    lines = [
        f"# Baseline Candidate Extraction ({dt.date.today().isoformat()})",
        "",
        "Status: proposed",
        "Generated by: `python .\\tools\\agent_archive.py baseline suggest`",
        "",
        "## Summary",
        "",
        f"- Indexed sessions: `{len(index_records)}`",
        f"- Markdown sessions scanned for text signals: `{scanned_count}`",
        f"- Sources represented: `{len(source_counts)}`",
        f"- Feedback file: `{feedback_path or 'none'}`",
        "",
        "## Source Mix",
        "",
    ]
    for source, count in source_counts.most_common():
        lines.append(f"- `{source}`: {count}")
    lines.extend(["", "## Kind Mix", ""])
    for kind, count in kind_counts.most_common():
        lines.append(f"- `{kind}`: {count}")
    lines.extend(["", "## Pilot Project Signals", ""])
    if project_hits:
        for slug, count in project_hits.most_common():
            lines.append(f"- `{slug}`: {count}")
    else:
        lines.append("- No configured pilot project names were detected in the archive index yet.")
    lines.extend(["", "## Text Signal Counts", ""])
    for group, signals in text_signals.items():
        lines.append(f"- `{group}`: {sum(signal.count for signal in signals)} hits across {len(signals)} scanned sessions")
    lines.extend(["", "## Predictions And Candidate Rules", ""])
    for prediction in predictions:
        lines.extend(render_prediction(prediction))
    lines.extend(
        [
            "",
            "## Calibration Loop",
            "",
            "Copy `baseline/calibration/feedback.example.toml` to `baseline/calibration/feedback.toml`, then mark each",
            "prediction as `accept`, `edit`, or `reject`. Rerun this command with `--feedback` to let the next report",
            "show where the system was right, wrong, or too vague.",
            "",
            "The first version only adjusts confidence and status. Later versions should compare prediction history",
            "against accepted feedback and make the next proposal sharper.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_prediction(prediction: Prediction) -> list[str]:
    lines = [
        f"### {prediction.title}",
        "",
        f"Prediction id: `{prediction.id}`",
        f"Status: {prediction.status}",
        f"Scope: {prediction.scope}",
        f"Risk: {prediction.risk}",
        f"Category: {prediction.category}",
        f"Confidence: {prediction.confidence:.2f}",
        f"Feedback: {prediction.feedback}",
        "",
        "Evidence:",
    ]
    for item in prediction.evidence:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Suggested baseline text:",
            prediction.text,
            "",
            "Promotion:",
            "- [ ] Accept",
            "- [ ] Edit and accept",
            "- [ ] Reject",
            "- [ ] Project-specific only",
            "",
        ]
    )
    return lines
