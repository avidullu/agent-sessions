"""Tests for deterministic fail-closed replay redaction (K9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sessions.baseline_redaction import (
    SCANNER_VERSION,
    _looks_hex,
    _shannon_entropy,
    build_preflight_report,
    preflight_to_dict,
    redact_text,
    result_to_report,
    scan_high_confidence,
    scan_high_entropy,
    write_preflight_report,
)


class TestHighConfidenceSecrets:
    @pytest.mark.parametrize(
        "text, expected_type",
        [
            # v0 patterns
            ("token ghp_" + "a" * 36 + " here", "github-token"),
            ("github_pat_" + "A" * 30, "github-pat"),
            ("key sk-" + "a" * 24, "openai-key"),
            ("aws AKIA" + "A" * 16, "aws-access-key"),
            ("slack xoxb-" + "1234567890abcd", "slack-token"),
            ("-----BEGIN OPENSSH PRIVATE KEY-----", "private-key-block"),
            ("db postgres://user:s3cretpw@host/db", "connection-string-password"),
            ("GITHUB_TOKEN=abcdef123456", "secret-env-assignment"),
            ("api_key: supersecretvalue", "secret-env-assignment"),
            # v1 patterns — extended denylist (issue #59)
            ("AIza" + "A" * 35 + " google key", "google-api-key"),
            ("charge using sk_live_" + "A" * 24, "stripe-live-key"),
            ("test mode rk_test_" + "0" * 24, "stripe-test-key"),
            (
                "Bearer eyJhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "dQw4w9WgXcQ",
                "jwt-token",
            ),
            ("Server=db.example.com;Database=mydb;Password=s3cret", "odbc-connection-string"),
            ("Data Source=.;Initial Catalog=DB;Pwd=p@ss", "odbc-connection-string"),
        ],
    )
    def test_each_high_confidence_pattern_detected(self, text: str, expected_type: str) -> None:
        findings = scan_high_confidence(text)
        assert any(f["type"] == expected_type for f in findings), findings

    def test_clean_text_has_no_findings(self) -> None:
        text = "Design a pipeline that ingests events and scores highlights. No secrets here."
        assert scan_high_confidence(text) == []

    def test_report_never_contains_secret_value(self) -> None:
        secret = "ghp_" + "z" * 36
        result = redact_text(f"my token is {secret} ok")
        report = result_to_report("archive/x.md", result)
        blob = json.dumps(report)
        assert secret not in blob
        assert report["blocked"] is True
        assert report["blocked_reasons"]


class TestRedactText:
    def test_blocks_on_high_confidence(self) -> None:
        result = redact_text("token ghp_" + "a" * 36)
        assert result.blocked is True
        assert result.scanner_version == SCANNER_VERSION

    def test_placeholders_for_low_risk_and_not_blocked(self) -> None:
        text = "Contact me at alice@example.com from /home/alice/project and again alice@example.com."
        result = redact_text(text)
        assert result.blocked is False
        assert "alice@example.com" not in result.redacted_text
        assert "/home/alice/project" not in result.redacted_text
        assert "<email-1>" in result.redacted_text
        assert "<path-2>" in result.redacted_text
        # repeated email reuses the same stable placeholder
        assert result.redacted_text.count("<email-1>") == 2

    def test_deterministic(self) -> None:
        text = "bob@example.com and /Users/bob/x and carol@example.com"
        first = redact_text(text)
        second = redact_text(text)
        assert first.redacted_text == second.redacted_text
        assert [p["id"] for p in first.placeholders] == [p["id"] for p in second.placeholders]


class TestPreflight:
    def test_aggregates_and_flags_blocked(self) -> None:
        items = [
            ("archive/a.md", "clean planning text with a table"),
            ("archive/b.md", "leak ghp_" + "a" * 36),
            ("archive/c.md", "email dev@example.com only"),
        ]
        preflight = build_preflight_report(items, generated_at="2026-07-07")
        assert preflight.total == 3
        assert preflight.blocked == 1
        assert preflight.allowed == 2
        # entries sorted by source_ref for stable output
        assert [e["source_ref"] for e in preflight.entries] == ["archive/a.md", "archive/b.md", "archive/c.md"]

    def test_write_report_is_deterministic_and_valueless(self, tmp_path: Path) -> None:
        secret = "AKIA" + "B" * 16
        items = [("archive/b.md", f"key {secret}")]
        preflight = build_preflight_report(items, generated_at="2026-07-07")
        path = tmp_path / "sub" / "redaction-preflight.json"
        write_preflight_report(path, preflight)
        assert path.exists()
        blob = path.read_text(encoding="utf-8")
        assert secret not in blob
        payload = json.loads(blob)
        assert payload["blocked"] == 1
        assert payload["scanner_version"] == SCANNER_VERSION

    def test_preflight_to_dict_roundtrips_counts(self) -> None:
        preflight = build_preflight_report([("archive/a.md", "clean")], generated_at="2026-07-07")
        payload = preflight_to_dict(preflight)
        assert payload["total"] == 1
        assert payload["blocked"] == 0


class TestV1ScannerVersion:
    def test_scanner_is_v1(self) -> None:
        assert SCANNER_VERSION == "redaction-v1"

    def test_scanner_version_in_report(self) -> None:
        result = redact_text("clean text")
        assert result.scanner_version == "redaction-v1"
        report = result_to_report("archive/x.md", result)
        assert report["scanner_version"] == "redaction-v1"


class TestEntropyHeuristic:
    def test_shannon_entropy_uniform(self) -> None:
        # 16 unique hex chars: uniform distribution → log2(16) = 4.0 bits
        entropy = _shannon_entropy("0123456789abcdef")
        assert 3.8 < entropy < 4.2

    def test_shannon_entropy_low_on_repeating(self) -> None:
        entropy = _shannon_entropy("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert entropy < 0.5

    def test_looks_hex_true(self) -> None:
        assert _looks_hex("deadbeef1234567890abcdef") is True

    def test_looks_hex_false_with_letters(self) -> None:
        assert _looks_hex("this-is-just-a-normal-sentence") is False

    def test_high_entropy_base64_blocked(self) -> None:
        # A high-entropy base64-looking token (random-like)
        token = "dGhpcyBpcyBhIHRlc3QgbWVzc2FnZSB3aXRoIGVudHJvcHk="
        result = redact_text(f"Use this token: {token}")
        assert result.blocked is True
        high_confidence_types = [f["type"] for f in result.high_confidence]
        assert "high-entropy-token" in high_confidence_types

    def test_low_entropy_not_blocked(self) -> None:
        # Low-entropy base64-ish string (all same character) — should NOT trigger.
        token = "AAAA" * 16
        result = redact_text(f"key: {token}")
        high_confidence_types = [f["type"] for f in result.high_confidence]
        assert "high-entropy-token" not in high_confidence_types

    def test_high_entropy_hex_blocked(self) -> None:
        # 40-char high-entropy hex string (like a SHA1)
        token = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        result = redact_text(f"hash: {token}")
        assert result.blocked is True
        high_confidence_types = [f["type"] for f in result.high_confidence]
        assert "high-entropy-token" in high_confidence_types

    def test_clean_session_no_false_positive(self) -> None:
        """A realistic planning transcript should not trigger entropy."""
        text = (
            "### 1. user\n\n"
            "Please design a CI pipeline for the project. Use GitHub Actions, "
            "run lint + type-check + test on Python 3.10 through 3.13, and "
            "produce a coverage report. No secrets should be in this prompt.\n\n"
            "### 2. assistant\n\n"
            "Here is the plan:\n\n"
            "| Step | Tool |\n"
            "|------|------|\n"
            "| Lint | ruff |\n"
            "| Type | mypy |\n"
            "| Test | pytest |\n"
        )
        result = redact_text(text)
        assert result.blocked is False

    def test_entropy_report_valueless(self) -> None:
        token = "dGhpcyBpcyBhIHRlc3QgbWVzc2FnZSB3aXRoIGVudHJvcHk="
        result = redact_text(f"token: {token}")
        report = result_to_report("archive/x.md", result)
        blob = json.dumps(report)
        assert token not in blob

    def test_scan_high_entropy_dedupes_repeated_tokens(self) -> None:
        token = "dGhpcyBpcyBhIHRlc3QgbWVzc2FnZSB3aXRoIGVudHJvcHk="
        findings = scan_high_entropy(f"{token} and again {token}")
        assert len(findings) == 1
        assert findings[0]["count"] == 2
