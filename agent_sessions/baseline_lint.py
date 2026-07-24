"""Read-only lint checks for baseline derived knowledge artifacts."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .baseline_promote import BASELINE_BLOCK_RE
from .baseline_settings import load_baseline_settings
from .config import ArchiveConfig

BEGIN_RE = re.compile(r'<!-- baseline:begin id="([^"]+)" -->')
END_RE = re.compile(r'<!-- baseline:end id="([^"]+)" -->')
MARKDOWN_LINK_RE = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
GENERATED_AT_RE = re.compile(r"\*\*(?:Generated at|Promoted):\*\*\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
CONTRADICTION_RE = re.compile(r"\b(?:CONTRADICTION|Contradicts):", re.IGNORECASE)

ROOT_LINK_PREFIXES = {
    "agent_sessions",
    "archive",
    "baseline",
    "config",
    "docs",
    "scripts",
    "tests",
    "tools",
}


@dataclass(frozen=True)
class BaselineBlock:
    block_id: str
    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True)
class LintFinding:
    rule_id: str
    severity: str
    path: str
    detail: str
    line: int | None = None


def repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def baseline_markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def parse_baseline_blocks(path: Path, text: str, repo_root: Path) -> tuple[list[BaselineBlock], list[LintFinding]]:
    findings: list[LintFinding] = []
    blocks: list[BaselineBlock] = []
    rel_path = repo_relative(path, repo_root)
    open_id: str | None = None
    open_line = 0
    open_start = 0
    seen_ids: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        begin = BEGIN_RE.search(line)
        end = END_RE.search(line)
        if begin:
            block_id = begin.group(1)
            if open_id is not None:
                findings.append(
                    LintFinding(
                        "W1-marker",
                        "error",
                        rel_path,
                        f"Nested marker `{block_id}` opened before `{open_id}` closed.",
                        index,
                    )
                )
                continue
            if block_id in seen_ids:
                findings.append(
                    LintFinding("W1-marker", "error", rel_path, f"Duplicate generated block id `{block_id}`.", index)
                )
            seen_ids.add(block_id)
            open_id = block_id
            open_line = index
            open_start = index - 1
        if end:
            block_id = end.group(1)
            if open_id is None:
                findings.append(
                    LintFinding("W1-marker", "error", rel_path, f"End marker `{block_id}` has no begin marker.", index)
                )
                continue
            if block_id != open_id:
                findings.append(
                    LintFinding(
                        "W1-marker",
                        "error",
                        rel_path,
                        f"End marker `{block_id}` does not match begin marker `{open_id}`.",
                        index,
                    )
                )
                open_id = None
                continue
            blocks.append(BaselineBlock(open_id, open_line, index, "\n".join(lines[open_start:index])))
            open_id = None
    if open_id is not None:
        findings.append(
            LintFinding("W1-marker", "error", rel_path, f"Begin marker `{open_id}` has no end marker.", open_line)
        )
    return blocks, findings


def generated_blocks(text: str) -> dict[str, str]:
    return {match.group(1): match.group(0).strip() for match in BASELINE_BLOCK_RE.finditer(text)}


def normalize_markdown_link(target: str) -> str:
    target = target.strip()
    if " " in target and not target.startswith("<"):
        target = target.split(" ", 1)[0]
    return target.strip("<>")


def resolve_markdown_link(source_path: Path, target: str, repo_root: Path) -> Path | None:
    target = normalize_markdown_link(target)
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https", "mailto", "data"}:
        return None
    path_part = unquote(parsed.path)
    if not path_part or path_part.startswith("#"):
        return None
    if path_part.startswith("/"):
        return repo_root / path_part.lstrip("/")
    first_part = Path(path_part).parts[0] if Path(path_part).parts else ""
    if first_part in ROOT_LINK_PREFIXES:
        return repo_root / path_part
    return source_path.parent / path_part


def lint_generated_links(path: Path, blocks: list[BaselineBlock], repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    rel_path = repo_relative(path, repo_root)
    for block in blocks:
        for match in MARKDOWN_LINK_RE.finditer(block.content):
            target_path = resolve_markdown_link(path, match.group(1), repo_root)
            if target_path is None:
                continue
            if not target_path.exists():
                findings.append(
                    LintFinding(
                        "W2-links",
                        "error",
                        rel_path,
                        f"Generated block `{block.block_id}` links to missing path `{normalize_markdown_link(match.group(1))}`.",
                        block.start_line,
                    )
                )
    return findings


def lint_stale_blocks(
    path: Path,
    blocks: list[BaselineBlock],
    repo_root: Path,
    *,
    today: dt.date,
    stale_days: int,
) -> list[LintFinding]:
    findings: list[LintFinding] = []
    rel_path = repo_relative(path, repo_root)
    for block in blocks:
        match = GENERATED_AT_RE.search(block.content)
        if not match:
            continue
        date_text = match.group(1)
        try:
            generated_on = dt.date.fromisoformat(date_text)
        except ValueError:
            findings.append(
                LintFinding(
                    "W3-generated-date",
                    "warning",
                    rel_path,
                    f"Generated block `{block.block_id}` has an invalid generated date `{date_text}`.",
                    block.start_line,
                )
            )
            continue
        age_days = (today - generated_on).days
        if age_days > stale_days:
            findings.append(
                LintFinding(
                    "W3-stale",
                    "warning",
                    rel_path,
                    f"Generated block `{block.block_id}` is {age_days} days old.",
                    block.start_line,
                )
            )
    return findings


def lint_contradiction_markers(path: Path, blocks: list[BaselineBlock], repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    rel_path = repo_relative(path, repo_root)
    for block in blocks:
        if CONTRADICTION_RE.search(block.content):
            findings.append(
                LintFinding(
                    "P6-contradiction",
                    "warning",
                    rel_path,
                    f"Generated block `{block.block_id}` contains an explicit contradiction marker.",
                    block.start_line,
                )
            )
    return findings


def inbound_project_links(root: Path, project_pages: list[Path]) -> set[Path]:
    inbound: set[Path] = set()
    page_targets = {page.resolve(): page for page in project_pages}
    for path in baseline_markdown_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = resolve_markdown_link(path, match.group(1), root.parent)
            if target is None:
                continue
            resolved = target.resolve()
            if resolved in page_targets and path.resolve() != resolved:
                inbound.add(page_targets[resolved])
    return inbound


def lint_orphan_project_pages(root: Path, repo_root: Path) -> list[LintFinding]:
    project_pages = sorted((root / "projects").glob("*/README.md"))
    inbound = inbound_project_links(root, project_pages)
    findings: list[LintFinding] = []
    for page in project_pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        has_generated_blocks = bool(generated_blocks(text))
        if page not in inbound and not has_generated_blocks:
            detail = "Project page has no inbound baseline links and no generated blocks yet."
            findings.append(LintFinding("W2-orphan", "warning", repo_relative(page, repo_root), detail))
    return findings


def lint_baseline(config: ArchiveConfig, *, stale_days: int = 90, today: dt.date | None = None) -> list[LintFinding]:
    settings = load_baseline_settings(config)
    findings: list[LintFinding] = []
    schema_path = settings.root / "SCHEMA.md"
    if not schema_path.exists():
        findings.append(
            LintFinding("W1-schema", "error", repo_relative(schema_path, config.repo_root), "baseline/SCHEMA.md missing.")
        )
    check_date = today or dt.date.today()
    for path in baseline_markdown_files(settings.root):
        text = path.read_text(encoding="utf-8", errors="replace")
        blocks, marker_findings = parse_baseline_blocks(path, text, config.repo_root)
        findings.extend(marker_findings)
        findings.extend(lint_generated_links(path, blocks, config.repo_root))
        findings.extend(lint_stale_blocks(path, blocks, config.repo_root, today=check_date, stale_days=stale_days))
        findings.extend(lint_contradiction_markers(path, blocks, config.repo_root))
    findings.extend(lint_orphan_project_pages(settings.root, config.repo_root))
    return findings


def render_lint_report(findings: list[LintFinding]) -> str:
    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    lines = [
        "# Baseline Lint Report",
        "",
        f"- Errors: `{errors}`",
        f"- Warnings: `{warnings}`",
        f"- Total findings: `{len(findings)}`",
        "",
    ]
    if not findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"
    lines.extend(["| Rule | Severity | Path | Line | Detail |", "|---|---|---|---|---|"])
    for finding in findings:
        line = "" if finding.line is None else str(finding.line)
        lines.append(
            f"| `{finding.rule_id}` | {finding.severity} | `{finding.path}` | {line} | {finding.detail} |"
        )
    return "\n".join(lines) + "\n"


def baseline_lint(
    config: ArchiveConfig,
    output: Path | None = None,
    stale_days: int = 90,
    dry_run: bool = False,
) -> int:
    findings = lint_baseline(config, stale_days=stale_days)
    report = render_lint_report(findings)
    if dry_run or output is None:
        print(report)
    else:
        target = output if output.is_absolute() else config.repo_root / output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8", newline="\n")
        print(f"Wrote {target}")
    return 1 if any(finding.severity == "error" for finding in findings) else 0
