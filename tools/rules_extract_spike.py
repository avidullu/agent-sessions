"""R1a validation spike: deterministic imperative-rule extraction dry-run.

Read-only over raw agent session stores. Measures whether D1 (regex +
deterministic clustering, no LLM) can recover the canonical cross-project
preferences of docs/RULES_EXTRACTION_AND_PUBLISH_PLAN.md SS3.4 from session
text alone, and gathers the role-split evidence behind D18.

Spike code (tracker row R1a): deliberately self-contained, never imported by
the package, and disposable once R1 lands. It writes nothing inside the repo;
the report goes wherever --report points (default: stdout only).

Usage:
  python tools/rules_extract_spike.py \
      --root claude=/mnt/c/Users/<user>/.claude/projects \
      --root codex=/mnt/c/Users/<user>/.codex/archived_sessions \
      [--limit-per-source 600] [--top 30] [--report /tmp/spike.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_sessions.baseline_redaction import redact_text  # noqa: E402
from agent_sessions.config import load_config  # noqa: E402
from agent_sessions.models import SessionMessage  # noqa: E402
from agent_sessions.sources.registry import get_extractor  # noqa: E402

CUE_RE = re.compile(
    r"\b(always|never|must not|mustn't|must|do not|don't|should not|shouldn't|should)\b"
)
NEGATIVE_CUES = {"never", "must not", "mustn't", "do not", "don't", "should not", "shouldn't"}
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
TOKEN_RE = re.compile(r"[a-z][a-z0-9_\-./]{1,}")
STOPWORDS = frozenset(
    """a an and are as at be been being by can could did do does for from had has have
    i if in into is it its just like me my of on or our so that the their them then
    there these they this to was we were what when which will with would you your
    always never must not do dont should shouldnt mustnt it's we're i'm""".split()
)
MIN_SENTENCE_LEN = 18
MAX_SENTENCE_LEN = 240
JACCARD_CLUSTER = 0.5
JACCARD_CONTRA = 0.5
GT_HIT_FRACTION = 0.5
# A cluster present in >= this fraction of one agent's scanned sessions is
# almost certainly injected instruction/system boilerplate, not behavior:
# instruction files ride into every session's context (F3 in issue #99).
ECHO_SATURATION = 0.8

# SS3.4 canonical preferences. `derivable` False = D12 "asserted" items that live
# only in user memory; recall is measured over the derivable subset only (F4).
GROUND_TRUTH: list[tuple[str, bool, frozenset[str]]] = [
    ("gt1-never-auto-merge", True, frozenset({"merge", "pr", "lgtm", "approval"})),
    ("gt2-session-handoff", True, frozenset({"session", "handoff", "resume"})),
    ("gt3-tracked-project-docs", True, frozenset({"tracker", "project", "doc", "status"})),
    ("gt4-one-pr-per-row", True, frozenset({"one", "pr", "per", "row", "small"})),
    ("gt5-no-paid-llm-training", True, frozenset({"train", "paid", "llm", "outputs"})),
    ("gt6-branch-from-main", False, frozenset({"branch", "main", "checkout", "pull"})),
    ("gt7-ci-green-before-move", False, frozenset({"ci", "green", "checks", "verify"})),
    ("gt8-format-on-save", False, frozenset({"format", "save", "editor", "diffs"})),
    ("gt9-isort-grouping", False, frozenset({"isort", "stdlib", "third-party", "imports"})),
    ("gt10-mypy-catches-more", True, frozenset({"mypy", "ruff", "catches"})),
]


@dataclass
class Candidate:
    normal: str
    tokens: frozenset[str]
    polarity: str
    sessions: set[str] = field(default_factory=set)
    agents: set[str] = field(default_factory=set)
    role_counts: Counter[str] = field(default_factory=Counter)
    count: int = 0
    sample: str = ""


@dataclass
class Cluster:
    members: list[Candidate]

    @property
    def tokens(self) -> frozenset[str]:
        merged: set[str] = set()
        for member in self.members:
            merged |= member.tokens
        return frozenset(merged)

    @property
    def polarity(self) -> str:
        return self.members[0].polarity

    @property
    def sessions(self) -> set[str]:
        out: set[str] = set()
        for member in self.members:
            out |= member.sessions
        return out

    @property
    def agents(self) -> set[str]:
        out: set[str] = set()
        for member in self.members:
            out |= member.agents
        return out

    @property
    def role_counts(self) -> Counter[str]:
        total: Counter[str] = Counter()
        for member in self.members:
            total += member.role_counts
        return total

    @property
    def count(self) -> int:
        return sum(member.count for member in self.members)

    @property
    def sample(self) -> str:
        return max(self.members, key=lambda m: m.count).sample


def safe_sample(sentence: str) -> str:
    result = redact_text(sentence)
    if result.blocked:
        return "<sample-blocked-by-redaction-v1>"
    return result.redacted_text


def polarity_of(sentence_lower: str) -> str:
    for cue in NEGATIVE_CUES:
        if cue in sentence_lower:
            return "negative"
    return "positive"


def normalize(sentence: str) -> tuple[str, frozenset[str]]:
    lowered = sentence.lower()
    tokens = [t for t in TOKEN_RE.findall(lowered) if t not in STOPWORDS]
    return " ".join(tokens), frozenset(tokens)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def iter_candidate_sentences(text: str) -> list[str]:
    out: list[str] = []
    for raw in SENTENCE_SPLIT_RE.split(text):
        sentence = raw.strip()
        if not MIN_SENTENCE_LEN <= len(sentence) <= MAX_SENTENCE_LEN:
            continue
        if sentence.count("`") > 4 or sentence.startswith(("|", "#", ">", "{", "<")):
            continue
        if CUE_RE.search(sentence.lower()):
            out.append(sentence)
    return out


def harvest(
    kind: str,
    files: list[Path],
    candidates: dict[tuple[str, str], Candidate],
    stats: Counter[str],
) -> None:
    extractor = get_extractor(kind)
    if extractor is None:
        stats[f"no-extractor:{kind}"] += 1
        return
    for path in files:
        try:
            session = extractor(path)
        except Exception:  # spike: unparseable files are skipped and counted
            stats[f"parse-errors:{kind}"] += 1
            continue
        stats[f"sessions:{kind}"] += 1
        message: SessionMessage
        for message in session.messages:
            role = (message.role or "unknown").lower()
            for sentence in iter_candidate_sentences(message.text):
                normal, tokens = normalize(sentence)
                if len(tokens) < 3:
                    continue
                pol = polarity_of(sentence.lower())
                key = (normal, pol)
                entry = candidates.get(key)
                if entry is None:
                    entry = Candidate(normal=normal, tokens=tokens, polarity=pol, sample=sentence)
                    candidates[key] = entry
                entry.count += 1
                entry.sessions.add(f"{kind}|{path}")
                entry.agents.add(kind)
                entry.role_counts[role] += 1


def cluster_candidates(candidates: list[Candidate], cap: int) -> list[Cluster]:
    ranked = sorted(candidates, key=lambda c: (-c.count, c.normal))[:cap]
    clusters: list[Cluster] = []
    for candidate in ranked:
        placed = False
        for cluster in clusters:
            if cluster.polarity == candidate.polarity and jaccard(cluster.tokens, candidate.tokens) >= JACCARD_CLUSTER:
                cluster.members.append(candidate)
                placed = True
                break
        if not placed:
            clusters.append(Cluster(members=[candidate]))
    return clusters


def agent_saturation(cluster: Cluster, sessions_by_kind: dict[str, int]) -> dict[str, float]:
    per_kind: Counter[str] = Counter(entry.split("|", 1)[0] for entry in cluster.sessions)
    return {
        kind: per_kind[kind] / sessions_by_kind[kind]
        for kind in per_kind
        if sessions_by_kind.get(kind)
    }


def is_echo_suspect(cluster: Cluster, sessions_by_kind: dict[str, int]) -> bool:
    return any(v >= ECHO_SATURATION for v in agent_saturation(cluster, sessions_by_kind).values())


def contradictions(clusters: list[Cluster]) -> list[tuple[Cluster, Cluster]]:
    pairs: list[tuple[Cluster, Cluster]] = []
    for i, left in enumerate(clusters):
        for right in clusters[i + 1 :]:
            if left.polarity != right.polarity and jaccard(left.tokens, right.tokens) >= JACCARD_CONTRA:
                pairs.append((left, right))
    return pairs


def ground_truth_hits(clusters: list[Cluster]) -> dict[str, bool]:
    hits: dict[str, bool] = {}
    for gt_id, _derivable, gt_tokens in GROUND_TRUTH:
        hit = any(
            len(gt_tokens & cluster.tokens) / len(gt_tokens) >= GT_HIT_FRACTION for cluster in clusters
        )
        hits[gt_id] = hit
    return hits


def recall_line(hits: dict[str, bool], ids: list[str], label: str) -> str:
    found = sum(1 for g in ids if hits[g])
    return f"- {label}: {found}/{len(ids)} recalled"


def score(cluster: Cluster) -> float:
    return float(len(cluster.sessions)) * (1.0 + 0.5 * (len(cluster.agents) - 1))


def parse_roots(pairs: list[str]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for pair in pairs:
        kind, _, raw = pair.partition("=")
        if not raw:
            raise SystemExit(f"--root expects KIND=PATH, got: {pair!r}")
        out.append((kind, Path(raw)))
    return out


def newest_files(root: Path, glob: str, limit: int) -> list[Path]:
    files = [p for p in root.glob(glob) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", default=[], help="extra KIND=PATH store root")
    parser.add_argument("--limit-per-source", type=int, default=600)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--cluster-cap", type=int, default=4000)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    config = load_config(repo_root)
    glob_by_kind = {source.kind: source.glob for source in config.sources}
    stores: list[tuple[str, Path, str]] = []
    for source in config.sources:
        for root in source.roots:
            if root.exists() and get_extractor(source.kind) is not None:
                stores.append((source.kind, root, source.glob))
    for kind, root in parse_roots(args.root):
        if not root.exists():
            raise SystemExit(f"--root path does not exist: {root}")
        stores.append((kind, root, glob_by_kind.get(kind, "**/*")))

    candidates: dict[tuple[str, str], Candidate] = {}
    stats: Counter[str] = Counter()
    for kind, root, glob in stores:
        files = newest_files(root, glob, args.limit_per_source)
        stats[f"files:{kind}"] += len(files)
        harvest(kind, files, candidates, stats)

    clusters = cluster_candidates(list(candidates.values()), args.cluster_cap)
    clusters.sort(key=lambda c: (-score(c), c.members[0].normal))
    contra = contradictions(clusters[: args.cluster_cap // 10])
    sessions_by_kind = {
        key.split(":", 1)[1]: count for key, count in stats.items() if key.startswith("sessions:")
    }
    non_echo = [c for c in clusters if not is_echo_suspect(c, sessions_by_kind)]
    hits_all = ground_truth_hits(clusters)
    hits_clean = ground_truth_hits(non_echo)

    derivable = [g for g, d, _ in GROUND_TRUTH if d]
    asserted = [g for g, d, _ in GROUND_TRUTH if not d]

    lines: list[str] = []
    lines.append("# R1a spike report — deterministic rule extraction dry-run")
    lines.append("")
    lines.append("## Corpus")
    for key in sorted(stats):
        lines.append(f"- {key}: {stats[key]}")
    lines.append(f"- unique candidates: {len(candidates)}")
    lines.append(f"- clusters formed: {len(clusters)}")
    lines.append(
        f"- echo-suspect clusters (>= {ECHO_SATURATION:.0%} of one agent's sessions): "
        f"{len(clusters) - len(non_echo)}"
    )
    lines.append("")
    lines.append("## Ground-truth recall (SS3.4 canonical set)")
    lines.append("All clusters (echo included):")
    lines.append(recall_line(hits_all, derivable, "session-derivable subset"))
    lines.append(recall_line(hits_all, asserted, "memory-only (asserted, D12) also seen"))
    lines.append("Non-echo clusters only (the honest mining number):")
    lines.append(recall_line(hits_clean, derivable, "session-derivable subset"))
    lines.append(recall_line(hits_clean, asserted, "memory-only (asserted, D12) also seen"))
    for gt_id, gt_derivable, _tokens in GROUND_TRUTH:
        marker = "derivable" if gt_derivable else "asserted"
        flags = f"{'HIT' if hits_all[gt_id] else 'miss'}/all, {'HIT' if hits_clean[gt_id] else 'miss'}/non-echo"
        lines.append(f"  - {gt_id} [{marker}]: {flags}")
    lines.append("")
    lines.append(f"## Top {args.top} clusters (samples pass redaction-v1)")
    for cluster in clusters[: args.top]:
        roles = dict(cluster.role_counts)
        sample = safe_sample(cluster.sample)
        echo_flag = " ECHO?" if is_echo_suspect(cluster, sessions_by_kind) else ""
        lines.append(
            f"- score={score(cluster):.1f} sessions={len(cluster.sessions)} "
            f"agents={sorted(cluster.agents)} polarity={cluster.polarity} roles={roles}{echo_flag}"
        )
        lines.append(f"  `{sample}`")
    lines.append("")
    lines.append(f"## Contradiction pairs (same topic, opposite polarity): {len(contra)}")
    for left, right in contra[:10]:
        lines.append(f"- `{safe_sample(left.sample)}`  <->  `{safe_sample(right.sample)}`")
    report = "\n".join(lines) + "\n"
    if args.report is not None:
        args.report.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
