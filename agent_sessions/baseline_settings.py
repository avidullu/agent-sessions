"""Baseline settings loading, scaffold templates, and artifact resolution."""

from __future__ import annotations

from pathlib import Path

from .baseline_types import BaselineSettings, Pilot
from .config import ArchiveConfig, read_toml, repo_path


BASELINE_CONFIG = Path("config/baseline.toml")
BASELINE_ROOT = Path("baseline")


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
