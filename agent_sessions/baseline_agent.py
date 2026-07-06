"""Evidence bundles for AI-assisted baseline proposal generation."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .baseline import load_index_records
from .baseline_settings import load_baseline_settings
from .config import ArchiveConfig
from .utils import archive_markdown_path


DEFAULT_OUTPUT_DIR = Path("baseline/evidence")


def baseline_bundle(
    config: ArchiveConfig,
    output_dir: Path | None = None,
    max_sessions: int = 12,
    max_chars_per_session: int = 2500,
    access_level: str = "session-only",
    focus: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    settings = load_baseline_settings(config)
    records = load_index_records(config)
    selected = select_records(records, focus=focus or [], max_sessions=max_sessions)
    bundle = {
        "bundle_id": f"{dt.date.today().isoformat()}-agent-baseline-bundle",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "access_level": access_level,
        "focus": focus or [],
        "constraints": bundle_constraints(access_level),
        "proposal_schema": proposal_schema(),
        "pilot_projects": [
            {"slug": pilot.slug, "kind": pilot.kind, "aliases": list(pilot.aliases), "notes": pilot.notes}
            for pilot in settings.pilots
        ],
        "evidence": [evidence_record(config, record, max_chars_per_session) for record in selected],
    }
    prompt = render_agent_prompt(bundle)
    target_dir = output_dir or config.repo_root / DEFAULT_OUTPUT_DIR
    if not target_dir.is_absolute():
        target_dir = config.repo_root / target_dir
    bundle_path = target_dir / f"{bundle['bundle_id']}.json"
    prompt_path = target_dir / f"{bundle['bundle_id']}.prompt.md"
    if dry_run:
        print(json.dumps(bundle, indent=2, ensure_ascii=False))
        print(prompt)
        print(f"Would write {bundle_path}")
        print(f"Would write {prompt_path}")
        return 0
    target_dir.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
    print(f"Wrote {bundle_path}")
    print(f"Wrote {prompt_path}")
    return 0


def select_records(records: list[dict[str, Any]], focus: list[str], max_sessions: int) -> list[dict[str, Any]]:
    focus_lower = [item.lower() for item in focus]

    def score(record: dict[str, Any]) -> tuple[int, int]:
        haystack = json.dumps(record, ensure_ascii=False).lower()
        focus_score = sum(1 for item in focus_lower if item in haystack)
        return (focus_score, int(record.get("messages") or 0))

    if focus_lower:
        records = [record for record in records if score(record)[0] > 0]
    by_score = sorted(records, key=score, reverse=True)
    selected: list[dict[str, Any]] = []
    per_source: dict[str, int] = {}
    for record in by_score:
        source = str(record.get("source", "unknown"))
        if per_source.get(source, 0) >= 4 and len(selected) < max_sessions // 2:
            continue
        selected.append(record)
        per_source[source] = per_source.get(source, 0) + 1
        if len(selected) >= max_sessions:
            break
    return selected


def evidence_record(config: ArchiveConfig, record: dict[str, Any], max_chars: int) -> dict[str, Any]:
    markdown = str(record.get("markdown", ""))
    markdown_path = archive_markdown_path(config.repo_root, markdown)
    excerpt = ""
    if markdown_path.exists():
        excerpt = markdown_path.read_text(encoding="utf-8", errors="replace")[:max_chars].rstrip()
    return {
        "source": record.get("source"),
        "kind": record.get("kind"),
        "messages": record.get("messages"),
        "markdown": markdown.replace("\\", "/"),
        "metadata": record.get("metadata", {}),
        "excerpt": excerpt,
    }


def bundle_constraints(access_level: str) -> list[str]:
    constraints = [
        "Draft proposals only; do not promote baseline entries.",
        "Every proposal must include evidence references.",
        "Classify scope, category, risk, confidence, and approval mode.",
        "Prefer concise baseline text over transcript summaries.",
        "Do not include secrets, credentials, private file contents, or one-off debug noise in suggested baseline text.",
    ]
    if access_level == "session-only":
        constraints.append("Use only the provided archive/session evidence bundle.")
    elif access_level == "repo-read-only":
        constraints.append("Repo inspection is read-only; do not write files or branches.")
    elif access_level == "write-candidates":
        constraints.append("Writes are limited to candidate files or PR branches; merging still requires approval.")
    return constraints


def proposal_schema() -> dict[str, Any]:
    return {
        "id": "stable.dotted.identifier",
        "title": "Short proposal title",
        "scope": "global | project:<slug> | user-profile | agent:<name>",
        "category": "repo-governance | regression-frameworks | architecture | docs | metacognition | prompt-patterns",
        "risk": "low | medium | high",
        "confidence": "0.00-1.00",
        "approval_mode": "strict | umbrella | auto-promote | observe-only",
        "evidence": ["relative archive or repo references"],
        "suggested_baseline_text": "Concise proposed guidance.",
        "open_questions": ["questions for the user before promotion"],
    }


def render_agent_prompt(bundle: dict[str, Any]) -> str:
    return f"""# AI Baseline Proposal Task

You are helping draft engineering baseline candidates from bounded evidence.

Access level: `{bundle['access_level']}`

## Constraints

{bullet_list(bundle['constraints'])}

## Output

Return Markdown candidate proposals. For each proposal include:

- stable id
- title
- scope
- category
- risk
- confidence
- approval mode
- evidence
- suggested baseline text
- open questions

## Proposal Schema

```json
{json.dumps(bundle['proposal_schema'], indent=2)}
```

## Evidence Bundle

Use the adjacent JSON bundle as the source of truth:
`{bundle['bundle_id']}.json`
"""


def bullet_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)
