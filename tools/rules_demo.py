"""Efficacy harness: run the shipped extract → ledger → cluster pipeline on real sessions.

Uses the SHIPPED modules (R1 rule_extractor, R1b rule_ledger, R2 rule_clusterer) end to end —
not a reimplementation — so the numbers reflect the actual feature. Emits a JSON report to --out.
This is the reproducible companion to ``docs/EFFICACY_CHECK_2026-07-23.md``: re-run against the same
roots after the R2a–R2c precision fixes and compare the metrics to quantify the improvement.

    PYTHONPATH=. python3 tools/rules_demo.py --limit-per-source 500 \
        --root claude=<claude-projects> --root codex=<codex-sessions> \
        --known <global CLAUDE.md> --known AGENTS.md --out /tmp/efficacy.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

from agent_sessions.rule_clusterer import (
    ClusteredRule,
    cluster_rules,
    clustered_rule_to_dict,
    find_contradictions,
)
from agent_sessions.rule_extractor import RawRule, extract_rules
from agent_sessions.rule_ledger import build_evidence_records
from agent_sessions.sources.registry import get_extractor
from agent_sessions.utils import canonical_agent

# §3.4 canonical cross-project preferences — the documented ground truth (spike parity).
GROUND_TRUTH: list[tuple[str, bool, frozenset[str]]] = [
    ("never-auto-merge PRs", True, frozenset({"merge", "pr", "lgtm", "approval"})),
    ("maintain SESSION_HANDOFF", True, frozenset({"session", "handoff", "resume"})),
    ("tracked project docs", True, frozenset({"tracker", "project", "doc", "status"})),
    ("one small PR per row", True, frozenset({"one", "pr", "per", "row", "small"})),
    ("never train on paid-LLM outputs", True, frozenset({"train", "paid", "llm", "outputs"})),
    ("branch from main, never commit direct", False, frozenset({"branch", "main", "checkout", "commit"})),
    ("verify CI green before moving on", False, frozenset({"ci", "green", "checks", "verify"})),
    ("format-on-save pollutes diffs", False, frozenset({"format", "save", "editor", "diffs"})),
    ("isort import grouping", False, frozenset({"isort", "stdlib", "imports", "grouping"})),
    ("mypy catches what ruff doesn't", True, frozenset({"mypy", "ruff", "catches"})),
]
GT_HIT_FRACTION = 0.5
SATURATION_THRESHOLD = 0.8

_GLOBS: dict[str, str] = {
    "claude": "**/*.jsonl",
    "codex": "**/*.jsonl",
    "deepseek_request_dump": "**/*.msg*.txt",
    "gemini_antigravity": "**/transcript*.jsonl",
    "grok": "**/chat_history.jsonl",
}


def parse_roots(pairs: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for pair in pairs:
        kind, _, raw = pair.partition("=")
        if not raw:
            raise SystemExit(f"--root expects KIND=PATH, got {pair!r}")
        out.append((kind, Path(raw)))
    return out


def newest(root: Path, glob: str, limit: int) -> list[Path]:
    files = [p for p in root.glob(glob) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def load_known_texts(paths: list[Path]) -> list[str]:
    texts: list[str] = []
    for p in paths:
        try:
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return texts


def max_saturation(cluster: ClusteredRule, sessions_by_agent: dict[str, int]) -> float:
    best = 0.0
    for agent, count in cluster.per_agent_sessions:
        total = sessions_by_agent.get(agent, 0)
        if total:
            best = max(best, count / total)
    return best


def gt_recall(clusters: list[ClusteredRule]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, derivable, gt_tokens in GROUND_TRUTH:
        hit = any(
            len(gt_tokens & set(c.topic_tokens)) / len(gt_tokens) >= GT_HIT_FRACTION
            for c in clusters
            if c.novel_sessions > 0
        )
        rows.append({"rule": label, "derivable": derivable, "recalled": hit})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Efficacy harness for the rule-mining pipeline.")
    ap.add_argument("--root", action="append", default=[], help="KIND=PATH store root")
    ap.add_argument("--limit-per-source", type=int, default=500)
    ap.add_argument("--known", action="append", default=[], help="instruction file for echo tagging")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    known_texts = load_known_texts([Path(k) for k in args.known])
    stats: Counter[str] = Counter()
    all_rules: list[RawRule] = []

    for kind, root in parse_roots(args.root):
        extractor = get_extractor(kind)
        if extractor is None or not root.exists():
            stats[f"skipped:{kind}"] += 1
            continue
        for path in newest(root, _GLOBS.get(kind, "**/*"), args.limit_per_source):
            try:
                session = extractor(path)
            except Exception:  # harness: unparseable files are skipped and counted
                stats[f"parse-error:{kind}"] += 1
                continue
            agent = canonical_agent({"kind": kind, "source": kind})
            rules = extract_rules(
                session, agent=agent, mtime=path.stat().st_mtime, known_instruction_texts=known_texts
            )
            all_rules.extend(rules)
            stats[f"sessions:{agent}"] += 1

    records, quarantined = build_evidence_records(all_rules)
    now = dt.datetime.now(dt.UTC)
    clusters = cluster_rules(records, now=now)
    contradictions = find_contradictions(clusters)

    sessions_by_agent = {k.split(":", 1)[1]: v for k, v in stats.items() if k.startswith("sessions:")}
    novel = [c for c in clusters if c.novel_sessions > 0]
    echo_only = [c for c in clusters if c.novel_sessions == 0 and c.echo_sessions > 0]
    genuine = [c for c in novel if max_saturation(c, sessions_by_agent) < SATURATION_THRESHOLD]
    suspect = [c for c in novel if max_saturation(c, sessions_by_agent) >= SATURATION_THRESHOLD]
    user_records, _ = build_evidence_records([r for r in all_rules if r.role == "user"])
    user_clusters = [c for c in cluster_rules(user_records, now=now) if c.novel_sessions > 0]

    def enrich(c: ClusteredRule) -> dict[str, object]:
        d = clustered_rule_to_dict(c)
        d["max_saturation"] = round(max_saturation(c, sessions_by_agent), 3)
        return d

    report: dict[str, object] = {
        "corpus": {
            "raw_rules": len(all_rules),
            "evidence_records": len(records),
            "quarantined_secrets": quarantined,
            "clusters_total": len(clusters),
            "novel_clusters": len(novel),
            "echo_only_clusters": len(echo_only),
            "saturation_suspect_clusters": len(suspect),
            "contradictions": len(contradictions),
            "sessions_by_agent": sessions_by_agent,
            "rule_roles": dict(Counter(r.role for r in all_rules)),
            "rule_novelty": dict(Counter(r.novelty for r in all_rules)),
        },
        "top_rules_raw": [enrich(c) for c in novel[: args.top]],
        "top_rules_genuine": [enrich(c) for c in genuine[: args.top]],
        "top_rules_user_role": [enrich(c) for c in user_clusters[: args.top]],
        "contradictions": [
            {"positive": p.positive_text, "negative": p.negative_text,
             "shared_tokens": list(p.shared_tokens), "overlap": p.overlap}
            for p in contradictions[:15]
        ],
        "ground_truth_recall": gt_recall(clusters),
    }
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    recalled = sum(1 for r in gt_recall(clusters) if r["recalled"])
    sys.stdout.write(
        f"sessions {sum(sessions_by_agent.values())} | records {len(records)} | "
        f"quarantined {quarantined} | clusters {len(clusters)} | contradictions {len(contradictions)} | "
        f"recall {recalled}/10\nwrote {args.out}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
