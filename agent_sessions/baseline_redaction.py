"""Deterministic, fail-closed redaction for replay egress (#25, K9).

Replay bundles are the only planned artifact that can carry full archived task
prompts and original deliverables to an external replayer or judge, so redaction
is a first-class safety deliverable, not a detail inside the bundle writer.

Two tiers:

* **High-confidence secrets** (API tokens, private keys, passworded connection
  strings, ``*TOKEN*``/``*SECRET*`` env assignments) are *blocking*. When any is
  found the bundle is refused — v0 is fail-closed with no silent redaction of a
  real secret.
* **Low-risk identifiers** (emails, private home-directory paths) are replaced
  in place with stable placeholders (``<email-1>``, ``<path-1>``) so the task
  meaning survives without leaking the raw value.

The redaction report records *counts, placeholder ids, blocked reasons, source
refs, and the scanner version* — never the secret values themselves — so the
report is safe even though it lives beside the (gitignored) bundle.

Detection is a pure function of the input text, so a given transcript always
produces the same report (supports gate R5-safety and deterministic bundles).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCANNER_VERSION = "redaction-v0"

# High-confidence secret forms. Any match blocks the bundle (fail-closed). The
# names are stable identifiers used in the report; the matched text is never
# stored or emitted.
HIGH_CONFIDENCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    (
        "connection-string-password",
        re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@[^\s/]+"),
    ),
    (
        "secret-env-assignment",
        re.compile(
            r"(?im)^\s*[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)[A-Za-z0-9_]*\s*[=:]\s*\S{4,}"
        ),
    ),
)

# Low-risk identifiers replaced with stable placeholders (bundle still allowed).
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
PRIVATE_PATH_RE = re.compile(r"(?:[A-Za-z]:\\Users\\[^\s\\\"']+|/home/[^\s/\"']+|/Users/[^\s/\"']+)")


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    blocked: bool
    high_confidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    placeholders: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    scanner_version: str = SCANNER_VERSION


def scan_high_confidence(text: str) -> list[dict[str, Any]]:
    """Return per-type counts of blocking secrets. Values are never included."""
    findings: list[dict[str, Any]] = []
    for name, pattern in HIGH_CONFIDENCE_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            findings.append({"type": name, "count": count})
    return findings


def _replace_with_placeholders(
    text: str,
    pattern: re.Pattern[str],
    prefix: str,
    counter_start: int,
) -> tuple[str, list[dict[str, Any]], int]:
    """Deterministically replace unique matches with ``<prefix-N>`` placeholders.

    Placeholder numbers are assigned in first-appearance order, so the same input
    always yields the same output."""
    mapping: dict[str, str] = {}
    order: list[str] = []
    counts: dict[str, int] = {}

    def _sub(match: re.Match[str]) -> str:
        value = match.group(0)
        counts[value] = counts.get(value, 0) + 1
        if value not in mapping:
            mapping[value] = f"<{prefix}-{counter_start + len(order)}>"
            order.append(value)
        return mapping[value]

    redacted = pattern.sub(_sub, text)
    placeholders = [
        {"type": prefix, "id": mapping[value], "count": counts[value]} for value in order
    ]
    return redacted, placeholders, counter_start + len(order)


def redact_text(text: str) -> RedactionResult:
    high_confidence = scan_high_confidence(text)
    # Placeholder replacement is applied regardless so a blocked report still
    # shows what *would* have been placeholdered, but a blocked bundle is never
    # written by the caller.
    redacted, email_ph, next_id = _replace_with_placeholders(text, EMAIL_RE, "email", 1)
    redacted, path_ph, _ = _replace_with_placeholders(redacted, PRIVATE_PATH_RE, "path", next_id)
    return RedactionResult(
        redacted_text=redacted,
        blocked=bool(high_confidence),
        high_confidence=tuple(high_confidence),
        placeholders=tuple(email_ph + path_ph),
    )


def result_to_report(source_ref: str, result: RedactionResult) -> dict[str, Any]:
    return {
        "source_ref": source_ref,
        "scanner_version": result.scanner_version,
        "blocked": result.blocked,
        "blocked_reasons": [
            f"high-confidence secret `{finding['type']}` x{finding['count']}"
            for finding in result.high_confidence
        ],
        "high_confidence": [dict(finding) for finding in result.high_confidence],
        "placeholders": [dict(item) for item in result.placeholders],
    }


@dataclass(frozen=True)
class RedactionPreflight:
    generated_at: str
    scanner_version: str
    total: int
    blocked: int
    allowed: int
    entries: tuple[dict[str, Any], ...]


def build_preflight_report(items: list[tuple[str, str]], *, generated_at: str) -> RedactionPreflight:
    """Run redaction over ``(source_ref, text)`` items and aggregate a report.

    ``generated_at`` is passed in (not read from the clock) so callers control
    stamping and tests stay deterministic."""
    entries: list[dict[str, Any]] = []
    blocked = 0
    for source_ref, text in items:
        result = redact_text(text)
        if result.blocked:
            blocked += 1
        entries.append(result_to_report(source_ref, result))
    entries.sort(key=lambda entry: str(entry["source_ref"]))
    return RedactionPreflight(
        generated_at=generated_at,
        scanner_version=SCANNER_VERSION,
        total=len(entries),
        blocked=blocked,
        allowed=len(entries) - blocked,
        entries=tuple(entries),
    )


def preflight_to_dict(preflight: RedactionPreflight) -> dict[str, Any]:
    return {
        "generated_at": preflight.generated_at,
        "scanner_version": preflight.scanner_version,
        "total": preflight.total,
        "blocked": preflight.blocked,
        "allowed": preflight.allowed,
        "entries": [dict(entry) for entry in preflight.entries],
    }


def write_preflight_report(path: Path, preflight: RedactionPreflight) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(preflight_to_dict(preflight), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
