"""Tests for the local Forgejo agent-provenance index."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import urllib.error
from collections.abc import Iterator
from email.message import Message
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from agent_sessions.provenance import (
    ForgejoClient,
    ProvenanceError,
    Store,
    format_summary,
    sync_repository,
)

FORGE = "https://forge.example.test"
REPO = "Example/project"
SHA_A = "a" * 40
SHA_B = "b" * 40


def identity_policy(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "forgejo-agent-identity-policy",
                "principals": [
                    {
                        "id": "codex",
                        "kind": "coding-agent",
                        "username": "codex-agent",
                        "display_name": "Codex Agent",
                        "email": "codex-agent@agents.invalid",
                    },
                    {
                        "id": "claude",
                        "kind": "coding-agent",
                        "username": "claude-agent",
                        "display_name": "Claude Agent",
                        "email": "claude-agent@agents.invalid",
                    },
                    {
                        "id": "provenance",
                        "kind": "read-only-service",
                        "username": "agent-provenance",
                        "display_name": "Reader",
                        "email": "reader@agents.invalid",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def pull(number: int = 7, *, actor: str = "avidullu", merged: bool = True) -> dict[str, Any]:
    return {
        "number": number,
        "title": "Explain provenance without guessing",
        "state": "closed" if merged else "open",
        "merged": merged,
        "user": {"login": actor},
        "merged_by": {"login": "avidullu"} if merged else None,
        "head": {"sha": SHA_A},
        "base": {"sha": SHA_B},
        "created_at": "2026-08-08T00:00:00Z",
        "updated_at": "2026-08-08T01:00:00Z",
        "merged_at": "2026-08-08T01:00:00Z" if merged else None,
        "body": "must never enter SQLite",
    }


def commit(
    *,
    sha: str = SHA_A,
    actor: str = "avidullu",
    name: str = "Avi Dullu",
    email: str = "avi@example.test",
    message: str = "change",
    signed: bool = False,
) -> dict[str, Any]:
    return {
        "sha": sha,
        "commit": {
            "author": {"name": name, "email": email, "date": "2026-08-08T00:00:00Z"},
            "committer": {"name": name, "email": email, "date": "2026-08-08T00:00:01Z"},
            "message": message,
            "verification": {
                "verified": signed,
                "reason": "signed" if signed else "gpg.error.not_signed_commit",
                "signer": {"login": actor} if signed else None,
                "payload": "not stored",
                "signature": "not stored",
            },
        },
        "author": {"login": actor},
        "committer": {"login": actor},
        "files": [{"filename": "private-name-not-stored"}],
    }


class FakeClient:
    def __init__(
        self,
        pulls: list[dict[str, Any]],
        commits: dict[int, list[dict[str, Any]]],
        reviews: dict[int, list[dict[str, Any]]] | None = None,
        comments: dict[int, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.base_url = FORGE
        self.pulls = {value["number"]: value for value in pulls}
        self.commits = commits
        self.reviews = reviews or {}
        self.comments = comments or {}

    def get(self, path: str) -> Any:
        number = int(path.rstrip("/").split("/")[-1])
        return self.pulls[number]

    def pages(self, path: str) -> list[Any]:
        if path.endswith("pulls?state=all&sort=recentupdate"):
            return list(self.pulls.values())
        parts = path.split("/")
        if parts[-1] == "commits":
            return self.commits.get(int(parts[-2]), [])
        if parts[-1] == "reviews":
            return self.reviews.get(int(parts[-2]), [])
        if parts[-1] == "comments":
            return self.comments.get(int(parts[-2]), [])
        raise AssertionError(path)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    value = Store(tmp_path / "state" / "provenance.sqlite3")
    value.open()
    yield value
    value.close()


def seed(store: Store, tmp_path: Path) -> None:
    assert store.seed_identity_policy(identity_policy(tmp_path / "identity.json")) == 2


def test_schema_is_private_versioned_and_contains_no_body_columns(tmp_path: Path) -> None:
    path = tmp_path / "private" / "index.sqlite3"
    with Store(path) as store:
        assert store.db.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {
            row["name"]
            for table in ("pull_requests", "reviews", "issue_comments", "commits")
            for row in store.db.execute(f"PRAGMA table_info({table})").fetchall()
        }
        assert "body" not in columns
        assert "message" not in columns
        assert "signature" not in columns
        assert "payload" not in columns
    if os.name == "nt":
        # Store.open() already ran the native ACL probe for both paths.
        assert path.is_file()
    else:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_store_rejects_symlink_and_unknown_schema(tmp_path: Path) -> None:
    target = tmp_path / "target.sqlite3"
    sqlite3.connect(target).close()
    link = tmp_path / "link.sqlite3"
    link.symlink_to(target)
    with pytest.raises(ProvenanceError, match="non-symlink"):
        Store(link).open()

    with sqlite3.connect(target) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(ProvenanceError, match="unsupported provenance schema"):
        Store(target).open()


def test_identity_policy_seeds_only_coding_agents_and_rejects_duplicate_identifiers(
    store: Store, tmp_path: Path
) -> None:
    seed(store, tmp_path)
    assert [value["agent_id"] for value in store.agent_rows()] == ["claude", "codex"]
    with pytest.raises(ProvenanceError, match="already belongs"):
        store.add_identifier("claude", "git_email", "codex-agent@agents.invalid", "bad")
    with pytest.raises(ProvenanceError, match="unknown agent"):
        store.add_identifier("grok", "git_email", "grok@example.test", "missing")


def test_policy_rejects_duplicate_json_keys_and_wrong_kind(store: Store, tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(ProvenanceError, match="duplicate JSON key"):
        store.seed_identity_policy(duplicate)
    wrong = tmp_path / "wrong.json"
    wrong.write_text('{"schema_version":1,"kind":"wrong","principals":[]}', encoding="utf-8")
    with pytest.raises(ProvenanceError, match="unsupported"):
        store.seed_identity_policy(wrong)


def test_sync_preserves_observed_avi_and_reports_unverified_claude_trailer(
    store: Store, tmp_path: Path
) -> None:
    seed(store, tmp_path)
    client = FakeClient(
        [pull()],
        {
            7: [
                commit(
                    message=(
                        "docs: explain\n\n"
                        "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
                    )
                )
            ]
        },
        reviews={7: [{"id": 2, "user": {"login": "reviewer"}, "state": "APPROVED", "submitted_at": "now"}]},
        comments={7: [{"id": 3, "user": {"login": "commenter"}, "created_at": "now", "updated_at": "now"}]},
    )
    assert sync_repository(store, client, REPO, [7]) == 1
    value = store.pull_summary(FORGE, REPO, 7)
    assert value["observed"]["submitted_by"] == "avidullu"
    assert value["attribution"]["status"] == "unknown"
    assert value["attribution"]["sources"] == ["declared-coauthor"]
    assert value["declared_coauthors"] == [
        {"sha": SHA_A, "name": "Claude Opus 5", "email": "noreply@anthropic.com"}
    ]
    assert value["reviews"][0]["actor_login"] == "reviewer"
    assert value["comment_actors"][0]["actor_login"] == "commenter"
    raw = store.path.read_bytes()
    assert b"must never enter SQLite" not in raw
    assert b"private-name-not-stored" not in raw
    assert b"not stored" not in raw
    rendered = format_summary(value)
    assert "Agent attribution: unknown" in rendered
    assert "Declared co-authors (unverified trailers)" in rendered


def test_repeated_coauthor_trailer_does_not_break_sync(store: Store, tmp_path: Path) -> None:
    seed(store, tmp_path)
    trailer = "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
    client = FakeClient([pull()], {7: [commit(message=f"docs: explain\n\n{trailer}{trailer}")]})

    assert sync_repository(store, client, REPO, [7]) == 1

    value = store.pull_summary(FORGE, REPO, 7)
    assert value["declared_coauthors"] == [
        {"sha": SHA_A, "name": "Claude Opus 5", "email": "noreply@anthropic.com"}
    ]


def test_exact_bot_actor_and_signed_identity_attribute_without_attestation(
    store: Store, tmp_path: Path
) -> None:
    seed(store, tmp_path)
    value = pull(actor="codex-agent", merged=False)
    client = FakeClient(
        [value],
        {
            7: [
                commit(
                    actor="codex-agent",
                    name="Codex Agent",
                    email="codex-agent@agents.invalid",
                    signed=True,
                )
            ]
        },
    )
    sync_repository(store, client, REPO)
    result = store.pull_summary(FORGE, REPO, 7)
    assert result["attribution"] == {
        "status": "attributed",
        "agent_ids": ["codex"],
        "confidence": "exact-forgejo-actor",
        "sources": ["forgejo-actor"],
        "evidence": [
            "forgejo_login:codex-agent",
        ],
    }
    assert store.list_by_agent("codex", REPO)[0]["pull_number"] == 7
    assert store.list_by_agent("claude") == []


def test_git_email_is_reported_as_unverified_when_forgejo_actor_is_human(
    store: Store, tmp_path: Path
) -> None:
    seed(store, tmp_path)
    client = FakeClient(
        [pull()],
        {7: [commit(name="Claude Agent", email="claude-agent@agents.invalid")]},
    )
    sync_repository(store, client, REPO, [7])
    value = store.pull_summary(FORGE, REPO, 7)
    assert value["attribution"]["agent_ids"] == ["claude"]
    assert value["attribution"]["confidence"] == "git-email-unverified"


def test_attestations_append_without_rewriting_observed_actor_and_conflicts_are_loud(
    store: Store, tmp_path: Path
) -> None:
    seed(store, tmp_path)
    sync_repository(store, FakeClient([pull()], {7: [commit()]}), REPO, [7])
    assert store.attest(FORGE, REPO, 7, "claude", "session-evidence", "session:exact-id", "agent-sessions")
    assert not store.attest(FORGE, REPO, 7, "claude", "session-evidence", "session:exact-id", "agent-sessions")
    value = store.pull_summary(FORGE, REPO, 7)
    assert value["observed"]["submitted_by"] == "avidullu"
    assert value["attribution"]["agent_ids"] == ["claude"]
    assert value["attribution"]["confidence"] == "owner-or-session-evidence"

    assert store.attest(FORGE, REPO, 7, "codex", "owner-attestation", "owner:correction-needed", "avidullu")
    conflicted = store.pull_summary(FORGE, REPO, 7)
    assert conflicted["attribution"]["status"] == "conflict"
    assert conflicted["attribution"]["agent_ids"] == ["claude", "codex"]


def test_sync_is_idempotent_and_refreshes_details(store: Store, tmp_path: Path) -> None:
    seed(store, tmp_path)
    client = FakeClient([pull()], {7: [commit()]})
    assert sync_repository(store, client, REPO, [7]) == 1
    client.reviews[7] = [{"id": 99, "user": {"login": "new-reviewer"}, "state": "COMMENT", "submitted_at": "later"}]
    assert sync_repository(store, client, REPO, [7]) == 1
    repository_id = store.repository_id(FORGE, REPO, create=False)
    assert store.db.execute(
        "SELECT COUNT(*) FROM pull_request_commits WHERE repository_id=? AND pull_number=7", (repository_id,)
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM reviews WHERE repository_id=? AND pull_number=7", (repository_id,)
    ).fetchone()[0] == 1
    assert store.db.execute("SELECT COUNT(*) FROM sync_runs WHERE status='success'").fetchone()[0] == 2


def test_failed_sync_is_recorded_without_partial_pull_state(store: Store) -> None:
    class BrokenClient(FakeClient):
        def pages(self, path: str) -> list[Any]:
            raise ProvenanceError("injected failure")

    client = BrokenClient([pull()], {7: [commit()]})
    with pytest.raises(ProvenanceError, match="injected failure"):
        sync_repository(store, client, REPO)
    assert store.db.execute("SELECT COUNT(*) FROM pull_requests").fetchone()[0] == 0
    row = store.db.execute("SELECT status, error FROM sync_runs").fetchone()
    assert row["status"] == "failed"
    assert row["error"] == "injected failure"


def test_invalid_inputs_fail_closed(store: Store, tmp_path: Path) -> None:
    seed(store, tmp_path)
    with pytest.raises(ProvenanceError, match="owner/name"):
        store.repository_id(FORGE, "not-a-repo", create=True)
    with pytest.raises(ProvenanceError, match="unique positive"):
        sync_repository(store, FakeClient([pull()], {7: []}), REPO, [7, 7])
    with pytest.raises(ProvenanceError, match="not indexed"):
        store.pull_summary(FORGE, REPO, 404)


def test_token_must_be_private_and_https(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("opaque\n", encoding="utf-8")
    if os.name != "nt":
        token.chmod(0o644)
        with pytest.raises(ProvenanceError, match="group/world"):
            ForgejoClient(FORGE, token)
    token.chmod(0o600)
    with pytest.raises(ProvenanceError, match="HTTPS"):
        ForgejoClient("http://forge.example.test", token)


def test_windows_acl_probe_fails_closed_on_unexpected_principal(tmp_path: Path) -> None:
    path = tmp_path / "secret"
    path.write_text("opaque", encoding="utf-8")
    completed = mock.Mock(returncode=3)
    with (
        mock.patch.object(os, "name", "nt"),
        mock.patch("agent_sessions.provenance.subprocess.run", return_value=completed) as run,
        pytest.raises(ProvenanceError, match="unexpected Windows principal"),
    ):
        from agent_sessions.provenance import _require_private_access

        _require_private_access(path)
    assert run.call_args.kwargs["env"]["AGENT_SESSIONS_PRIVATE_PATH"] == str(path)
    assert str(path) not in run.call_args.args[0]


def test_forgejo_client_get_pages_and_errors(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("opaque\n", encoding="utf-8")
    token.chmod(0o600)
    client = ForgejoClient(FORGE, token)

    class Response:
        status = 200

        def __init__(self, payload: object):
            self.payload = json.dumps(payload).encode()

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit > len(self.payload)
            return self.payload

    calls = 0

    def fake_urlopen(request: object, timeout: int) -> Response:
        nonlocal calls
        assert timeout == 30
        assert "opaque" not in str(request)
        calls += 1
        return Response([{"id": 1}] if calls == 1 else [])

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert client.pages("/items", limit=1) == [{"id": 1}]

    error = urllib.error.HTTPError("url", 403, "forbidden", Message(), None)
    error.read = mock.Mock(return_value=b'{"message":"denied"}')  # type: ignore[method-assign]
    with mock.patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ProvenanceError, match="returned 403: denied"):
            client.get("/denied")


def test_database_default_can_be_overridden_without_touching_repo(tmp_path: Path) -> None:
    path = tmp_path / "elsewhere" / "state.sqlite3"
    with Store(path) as store:
        assert store.path == path.resolve()
    assert not list(tmp_path.glob("*.sqlite3"))
    assert os.path.exists(path)
