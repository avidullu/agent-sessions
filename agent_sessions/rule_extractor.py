"""Role-aware imperative-rule extraction from a single session (R1, D18).

Deterministic (regex + normalization, no LLM — D1, confirmed on R1a evidence).
Designed to be invoked per session at export time (D17): stateless, cheap, and
operating on one :class:`~agent_sessions.models.ExtractedSession` so the
exporting machine mines each body while it is guaranteed present.  Corpus-level
concerns — clustering, scoring, the >=80% echo-saturation rule — belong to the
clusterer and ledger stages (R1b/R2), not here.

Echo controls implemented at this layer (D18):

- text inside ``<!-- baseline:... -->`` marker blocks is skipped entirely
  (generated content is never evidence);
- sentences whose normalized form matches a caller-supplied set of known
  instruction texts (CLAUDE.md, AGENTS.md, ...) are tagged ``echo`` rather
  than ``novel`` — the R1a spike showed such text arrives under ``user`` /
  ``request-prompt`` roles, so role weighting alone cannot catch it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from .models import ExtractedSession

NOVELTY_NOVEL = "novel"
NOVELTY_ECHO = "echo"
POLARITY_POSITIVE = "positive"
POLARITY_NEGATIVE = "negative"

CUE_RE = re.compile(
    r"\b(always|never|must not|mustn't|must|do not|don't|should not|shouldn't|should)\b"
)
NEGATIVE_CUES = ("must not", "mustn't", "do not", "don't", "should not", "shouldn't", "never")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
TOKEN_RE = re.compile(r"[a-z][a-z0-9_\-./]{1,}")
MARKER_BLOCK_RE = re.compile(
    r"<!--\s*baseline:(?:[\w-]+:)*begin\b.*?<!--\s*baseline:(?:[\w-]+:)*end\b[^>]*-->",
    re.DOTALL,
)
# A Windows cwd: drive-letter prefix (``C:\`` or ``C:/``) or any backslash.
# ``PureWindowsPath`` then handles both separators and mixed forms.
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]|\\")
STOPWORDS = frozenset(
    """a an and are as at be been being by can could did do does for from had has have
    i if in into is it its just like me my of on or our so that the their them then
    there these they this to was we were what when which will with would you your
    always never must not dont don should shouldn shouldnt mustn mustnt""".split()
)
MIN_SENTENCE_LEN = 18
MAX_SENTENCE_LEN = 240
MIN_TOPIC_TOKENS = 3
_SKIP_PREFIXES = ("|", "#", ">", "{", "<")


@dataclass(frozen=True)
class RawRule:
    """One imperative statement with full provenance (R1 contract)."""

    text: str
    normalized: str
    polarity: str
    tokens: tuple[str, ...]
    role: str
    novelty: str
    session_id: str
    agent: str
    project: str
    mtime: float


def strip_marker_blocks(text: str) -> str:
    """Drop generated ``<!-- baseline:... -->`` content before mining (D18)."""
    return MARKER_BLOCK_RE.sub(" ", text)


def iter_imperative_sentences(text: str) -> list[str]:
    """Split ``text`` into candidate imperative sentences, filtered for noise."""
    out: list[str] = []
    for raw in SENTENCE_SPLIT_RE.split(text):
        sentence = raw.strip()
        if not MIN_SENTENCE_LEN <= len(sentence) <= MAX_SENTENCE_LEN:
            continue
        if sentence.count("`") > 4 or sentence.startswith(_SKIP_PREFIXES):
            continue
        if CUE_RE.search(sentence.lower()):
            out.append(sentence)
    return out


def polarity_of(sentence: str) -> str:
    lowered = sentence.lower()
    for cue in NEGATIVE_CUES:
        if cue in lowered:
            return POLARITY_NEGATIVE
    return POLARITY_POSITIVE


def normalize_rule(sentence: str) -> tuple[str, tuple[str, ...]]:
    """Return (normalized text, sorted topic tokens) for clustering and echo tests."""
    lowered = sentence.lower()
    tokens = [t for t in TOKEN_RE.findall(lowered) if t not in STOPWORDS]
    return " ".join(tokens), tuple(sorted(set(tokens)))


def build_known_normals(texts: Iterable[str]) -> frozenset[str]:
    """Normalize known instruction texts into the echo-matching set (D18)."""
    normals: set[str] = set()
    for text in texts:
        for sentence in iter_imperative_sentences(strip_marker_blocks(text)):
            normalized, _tokens = normalize_rule(sentence)
            if normalized:
                normals.add(normalized)
    return frozenset(normals)


def session_id_from_metadata(metadata: dict[str, Any]) -> str:
    value = metadata.get("session_id", "")
    return str(value) if value else ""


def project_from_metadata(metadata: dict[str, Any]) -> str:
    """Best-effort project slug from the session ``cwd`` (scope logic is R3's).

    Windows paths — a drive-letter prefix or any backslash, including the
    ``C:/Users/...`` forward-slash form — are parsed with ``PureWindowsPath``;
    everything else as POSIX. Both extract the final path component.
    """
    cwd = metadata.get("cwd", "")
    if not cwd:
        return ""
    text = str(cwd).strip()
    parser = PureWindowsPath if _WINDOWS_PATH_RE.search(text) else PurePosixPath
    return parser(text).name.lower()


def extract_rules(
    session: ExtractedSession,
    *,
    agent: str,
    mtime: float,
    known_instruction_texts: Sequence[str] = (),
) -> list[RawRule]:
    """Mine one session for imperative rules with role + novelty provenance.

    Deterministic: rules are returned in message order, then sentence order.
    """
    known_normals = build_known_normals(known_instruction_texts)
    session_id = session_id_from_metadata(session.metadata)
    project = project_from_metadata(session.metadata)
    rules: list[RawRule] = []
    for message in session.messages:
        role = (message.role or "unknown").lower()
        for sentence in iter_imperative_sentences(strip_marker_blocks(message.text)):
            normalized, tokens = normalize_rule(sentence)
            if len(tokens) < MIN_TOPIC_TOKENS:
                continue
            novelty = NOVELTY_ECHO if normalized in known_normals else NOVELTY_NOVEL
            rules.append(
                RawRule(
                    text=sentence,
                    normalized=normalized,
                    polarity=polarity_of(sentence),
                    tokens=tokens,
                    role=role,
                    novelty=novelty,
                    session_id=session_id,
                    agent=agent,
                    project=project,
                    mtime=mtime,
                )
            )
    return rules
