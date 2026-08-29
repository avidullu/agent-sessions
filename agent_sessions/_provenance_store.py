"""SQLite storage and attribution queries for Forgejo provenance."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._provenance_common import (
    ProvenanceError,
    _bounded,
    _harden_private_access,
    _json,
    _now,
    _one_line,
    _positive_integer,
    _read_regular,
    _require_private_access,
    _same_file,
)

SCHEMA_VERSION = 1
DEFAULT_DATABASE = Path("~/.local/share/agent-sessions/forgejo-provenance.sqlite3").expanduser()
MAX_POLICY_BYTES = 256 * 1024
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
AGENT_ID = re.compile(r"[a-z][a-z0-9-]{1,38}[a-z0-9]\Z")
SHA = re.compile(r"[0-9a-f]{40,64}\Z")
CO_AUTHOR = re.compile(
    r"^Co-Authored-By:\s*(?P<name>[^<\r\n]{1,200}?)\s*<(?P<email>[^<>\s]{3,254})>\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class Attribution:
    status: str
    agent_ids: tuple[str, ...]
    confidence: str
    sources: tuple[str, ...]
    evidence: tuple[str, ...]


class Store:
    """Versioned SQLite store with append-only attestations."""

    def __init__(self, path: Path = DEFAULT_DATABASE):
        # Keep the caller-supplied leaf unresolved so open() can reject a
        # symlink instead of silently following it into another trust domain.
        self.path = path.expanduser().absolute()
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> Store:
        self.open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ProvenanceError("database is not open")
        return self._connection

    def open(self) -> None:
        if self._connection is not None:
            return
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_info = self.path.parent.lstat()
        if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
            raise ProvenanceError(f"database parent must be a non-symlink directory: {self.path.parent}")
        if os.name == "nt":
            _harden_private_access(self.path.parent)
        else:
            self.path.parent.chmod(0o700)
            _require_private_access(self.path.parent)
        flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_BINARY", 0)
        created = False
        try:
            descriptor = os.open(self.path, flags)
        except FileNotFoundError:
            try:
                descriptor = os.open(self.path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except OSError as exc:
                raise ProvenanceError(f"cannot create private database {self.path}: {exc}") from exc
        except OSError as exc:
            raise ProvenanceError(f"database must be a regular non-symlink file: {self.path}: {exc}") from exc
        connection: sqlite3.Connection | None = None
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise ProvenanceError(f"database must be a regular non-symlink file: {self.path}")
            _same_file(self.path, opened, "database")
            if os.name == "nt" and created:
                _harden_private_access(self.path)
            else:
                _require_private_access(self.path, opened)
            _same_file(self.path, opened, "database")
            connection = sqlite3.connect(self.path)
            _same_file(self.path, opened, "database")
        except Exception:
            if connection is not None:
                connection.close()
            raise
        finally:
            os.close(descriptor)
        if connection is None:
            raise ProvenanceError(f"cannot open private database: {self.path}")
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA secure_delete = ON")
            if os.name != "nt" or not created:
                _require_private_access(self.path)
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version not in {0, SCHEMA_VERSION}:
                raise ProvenanceError(f"unsupported provenance schema version {version}")
            if version == 0:
                self._create_schema(connection)
        except Exception:
            connection.close()
            raise
        self._connection = connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                source TEXT NOT NULL,
                policy_sha256 TEXT NOT NULL,
                CHECK(length(agent_id) BETWEEN 3 AND 40)
            );
            CREATE TABLE agent_identifiers (
                kind TEXT NOT NULL,
                value TEXT NOT NULL COLLATE NOCASE,
                agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                source TEXT NOT NULL,
                PRIMARY KEY(kind, value),
                CHECK(kind IN ('forgejo_login', 'git_email'))
            );
            CREATE TABLE repositories (
                id INTEGER PRIMARY KEY,
                forgejo_url TEXT NOT NULL,
                full_name TEXT NOT NULL,
                UNIQUE(forgejo_url, full_name)
            );
            CREATE TABLE pull_requests (
                repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                state TEXT NOT NULL,
                merged INTEGER NOT NULL CHECK(merged IN (0, 1)),
                author_login TEXT NOT NULL,
                merged_by_login TEXT NOT NULL,
                head_sha TEXT NOT NULL,
                base_sha TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                merged_at TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY(repository_id, number)
            );
            CREATE TABLE commits (
                repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                sha TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_email TEXT NOT NULL,
                committer_name TEXT NOT NULL,
                committer_email TEXT NOT NULL,
                forgejo_author_login TEXT NOT NULL,
                forgejo_committer_login TEXT NOT NULL,
                signature_verified INTEGER NOT NULL CHECK(signature_verified IN (0, 1)),
                signature_reason TEXT NOT NULL,
                signer_login TEXT NOT NULL,
                authored_at TEXT NOT NULL,
                committed_at TEXT NOT NULL,
                PRIMARY KEY(repository_id, sha)
            );
            CREATE TABLE pull_request_commits (
                repository_id INTEGER NOT NULL,
                pull_number INTEGER NOT NULL,
                sha TEXT NOT NULL,
                position INTEGER NOT NULL CHECK(position >= 0),
                PRIMARY KEY(repository_id, pull_number, sha),
                FOREIGN KEY(repository_id, pull_number)
                    REFERENCES pull_requests(repository_id, number) ON DELETE CASCADE,
                FOREIGN KEY(repository_id, sha)
                    REFERENCES commits(repository_id, sha) ON DELETE CASCADE
            );
            CREATE TABLE commit_coauthors (
                repository_id INTEGER NOT NULL,
                sha TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY(repository_id, sha, email),
                FOREIGN KEY(repository_id, sha)
                    REFERENCES commits(repository_id, sha) ON DELETE CASCADE
            );
            CREATE TABLE reviews (
                repository_id INTEGER NOT NULL,
                pull_number INTEGER NOT NULL,
                review_id INTEGER NOT NULL,
                actor_login TEXT NOT NULL,
                state TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                PRIMARY KEY(repository_id, pull_number, review_id),
                FOREIGN KEY(repository_id, pull_number)
                    REFERENCES pull_requests(repository_id, number) ON DELETE CASCADE
            );
            CREATE TABLE issue_comments (
                repository_id INTEGER NOT NULL,
                pull_number INTEGER NOT NULL,
                comment_id INTEGER NOT NULL,
                actor_login TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(repository_id, pull_number, comment_id),
                FOREIGN KEY(repository_id, pull_number)
                    REFERENCES pull_requests(repository_id, number) ON DELETE CASCADE
            );
            CREATE TABLE attestations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id INTEGER NOT NULL,
                pull_number INTEGER NOT NULL,
                agent_id TEXT NOT NULL REFERENCES agents(agent_id),
                source TEXT NOT NULL CHECK(source IN ('owner-attestation', 'session-evidence')),
                evidence_ref TEXT NOT NULL,
                attested_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(repository_id, pull_number)
                    REFERENCES pull_requests(repository_id, number) ON DELETE CASCADE,
                UNIQUE(repository_id, pull_number, agent_id, source, evidence_ref, attested_by)
            );
            CREATE TABLE sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id INTEGER NOT NULL REFERENCES repositories(id),
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                pull_count INTEGER NOT NULL CHECK(pull_count >= 0),
                status TEXT NOT NULL CHECK(status IN ('success', 'failed')),
                error TEXT NOT NULL
            );
            PRAGMA user_version = 1;
            COMMIT;
            """
        )

    def seed_identity_policy(self, policy_path: Path) -> int:
        raw = _read_regular(policy_path, maximum=MAX_POLICY_BYTES)
        data = _json(raw, str(policy_path))
        if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("kind") != "forgejo-agent-identity-policy":
            raise ProvenanceError("identity policy has an unsupported schema or kind")
        principals = data.get("principals")
        if not isinstance(principals, list):
            raise ProvenanceError("identity policy principals must be a list")
        policy_sha = hashlib.sha256(raw).hexdigest()
        policy_rows: list[tuple[str, str, str, str]] = []
        desired_identifiers: set[tuple[str, str, str]] = set()
        identifier_owners: dict[tuple[str, str], str] = {}
        for index, principal in enumerate(principals):
            if not isinstance(principal, dict):
                raise ProvenanceError(f"identity policy principal {index} is not an object")
            agent_id = _one_line(principal.get("id"), f"principal {index} id", allow_empty=False)
            if not AGENT_ID.fullmatch(agent_id) or principal.get("kind") != "coding-agent":
                continue
            display = _one_line(principal.get("display_name"), f"principal {agent_id} display_name", allow_empty=False)
            username = _one_line(principal.get("username"), f"principal {agent_id} username", allow_empty=False)
            email = _one_line(principal.get("email"), f"principal {agent_id} email", allow_empty=False)
            policy_rows.append((agent_id, display, username, email))
            for kind, value in (("forgejo_login", username), ("git_email", email)):
                key = (kind, value.casefold())
                existing_owner = identifier_owners.get(key)
                if existing_owner is not None and existing_owner != agent_id:
                    raise ProvenanceError(f"identifier {kind}:{value} belongs to multiple policy agents")
                identifier_owners[key] = agent_id
                desired_identifiers.add((kind, value.casefold(), agent_id))
        with self.db:
            stale = self.db.execute(
                "SELECT kind, value, agent_id FROM agent_identifiers WHERE source LIKE 'identity-policy:%'"
            ).fetchall()
            for identifier in stale:
                identity = (
                    str(identifier["kind"]),
                    str(identifier["value"]).casefold(),
                    str(identifier["agent_id"]),
                )
                if identity not in desired_identifiers:
                    self.db.execute(
                        "DELETE FROM agent_identifiers WHERE kind=? AND value=?",
                        (identifier["kind"], identifier["value"]),
                    )
            for agent_id, display, username, email in policy_rows:
                self.db.execute(
                    "INSERT INTO agents(agent_id, display_name, source, policy_sha256) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(agent_id) DO UPDATE SET display_name=excluded.display_name, "
                    "source=excluded.source, policy_sha256=excluded.policy_sha256",
                    (agent_id, display, str(policy_path), policy_sha),
                )
                for kind, value in (("forgejo_login", username), ("git_email", email)):
                    existing = self.db.execute(
                        "SELECT agent_id FROM agent_identifiers WHERE kind=? AND value=?",
                        (kind, value),
                    ).fetchone()
                    if existing is not None and existing["agent_id"] != agent_id:
                        raise ProvenanceError(f"identifier {kind}:{value} already belongs to {existing['agent_id']}")
                    self.db.execute(
                        "INSERT INTO agent_identifiers(kind, value, agent_id, source) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(kind, value) DO UPDATE SET agent_id=excluded.agent_id, source=excluded.source",
                        (kind, value, agent_id, f"identity-policy:{policy_sha}"),
                    )
        return len(policy_rows)

    def add_identifier(self, agent_id: str, kind: str, value: str, source: str) -> None:
        if kind not in {"forgejo_login", "git_email"}:
            raise ProvenanceError("identifier kind must be forgejo_login or git_email")
        value = _one_line(value, "identifier value", maximum=254, allow_empty=False)
        source = _one_line(source, "identifier source", allow_empty=False)
        with self.db:
            if self.db.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone() is None:
                raise ProvenanceError(f"unknown agent: {agent_id}")
            existing = self.db.execute(
                "SELECT agent_id FROM agent_identifiers WHERE kind=? AND value=?", (kind, value)
            ).fetchone()
            if existing is not None and existing["agent_id"] != agent_id:
                raise ProvenanceError(f"identifier already belongs to {existing['agent_id']}")
            self.db.execute(
                "INSERT OR REPLACE INTO agent_identifiers(kind, value, agent_id, source) VALUES (?, ?, ?, ?)",
                (kind, value, agent_id, source),
            )

    def repository_id(self, forgejo_url: str, full_name: str, *, create: bool) -> int:
        if not REPOSITORY.fullmatch(full_name):
            raise ProvenanceError("repository must be owner/name")
        row = self.db.execute(
            "SELECT id FROM repositories WHERE forgejo_url=? AND full_name=?",
            (forgejo_url, full_name),
        ).fetchone()
        if row is not None:
            return int(row["id"])
        if not create:
            raise ProvenanceError(f"repository is not indexed: {full_name}")
        cursor = self.db.execute(
            "INSERT INTO repositories(forgejo_url, full_name) VALUES (?, ?)",
            (forgejo_url, full_name),
        )
        if cursor.lastrowid is None:
            raise ProvenanceError("SQLite did not return a repository row ID")
        return cursor.lastrowid

    def upsert_pull(self, forgejo_url: str, repository: str, value: dict[str, Any]) -> int:
        repository_id = self.repository_id(forgejo_url, repository, create=True)
        number = _positive_integer(value.get("number"), "pull request number")
        author = value.get("user") or {}
        merged_by = value.get("merged_by") or {}
        head = value.get("head") or {}
        base = value.get("base") or {}
        if not all(isinstance(item, dict) for item in (author, merged_by, head, base)):
            raise ProvenanceError(f"pull request {number} has malformed identity fields")
        fields = (
            repository_id,
            number,
            _one_line(value.get("title", ""), "pull title", maximum=500),
            _one_line(value.get("state", ""), "pull state", maximum=30),
            int(value.get("merged") is True),
            _one_line(author.get("login", ""), "pull author", maximum=100),
            _one_line(merged_by.get("login", ""), "pull merger", maximum=100),
            _one_line(head.get("sha", ""), "head SHA", maximum=64),
            _one_line(base.get("sha", ""), "base SHA", maximum=64),
            _one_line(value.get("created_at", ""), "pull created_at", maximum=50),
            _one_line(value.get("updated_at", ""), "pull updated_at", maximum=50),
            _one_line(value.get("merged_at", ""), "pull merged_at", maximum=50),
            _now(),
        )
        if fields[7] and not SHA.fullmatch(fields[7]):
            raise ProvenanceError(f"pull request {number} has an invalid head SHA")
        if fields[8] and not SHA.fullmatch(fields[8]):
            raise ProvenanceError(f"pull request {number} has an invalid base SHA")
        self.db.execute(
            """
            INSERT INTO pull_requests(
                repository_id, number, title, state, merged, author_login,
                merged_by_login, head_sha, base_sha, created_at, updated_at,
                merged_at, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repository_id, number) DO UPDATE SET
                title=excluded.title, state=excluded.state, merged=excluded.merged,
                author_login=excluded.author_login,
                merged_by_login=excluded.merged_by_login,
                head_sha=excluded.head_sha, base_sha=excluded.base_sha,
                created_at=excluded.created_at, updated_at=excluded.updated_at,
                merged_at=excluded.merged_at, synced_at=excluded.synced_at
            """,
            fields,
        )
        return number

    def replace_pull_details(
        self,
        forgejo_url: str,
        repository: str,
        number: int,
        commits: Sequence[dict[str, Any]],
        reviews: Sequence[dict[str, Any]],
        comments: Sequence[dict[str, Any]],
    ) -> None:
        repository_id = self.repository_id(forgejo_url, repository, create=False)
        self.db.execute(
            "DELETE FROM pull_request_commits WHERE repository_id=? AND pull_number=?", (repository_id, number)
        )
        self.db.execute("DELETE FROM reviews WHERE repository_id=? AND pull_number=?", (repository_id, number))
        self.db.execute("DELETE FROM issue_comments WHERE repository_id=? AND pull_number=?", (repository_id, number))
        for position, item in enumerate(commits):
            self._upsert_commit(repository_id, number, position, item)
        for item in reviews:
            self._insert_review(repository_id, number, item)
        for item in comments:
            self._insert_comment(repository_id, number, item)
        self.db.execute(
            "DELETE FROM commits WHERE repository_id=? AND NOT EXISTS ("
            "SELECT 1 FROM pull_request_commits links "
            "WHERE links.repository_id=commits.repository_id AND links.sha=commits.sha)",
            (repository_id,),
        )

    def _upsert_commit(self, repository_id: int, pull_number: int, position: int, item: dict[str, Any]) -> None:
        sha = _one_line(item.get("sha"), "commit SHA", maximum=64, allow_empty=False)
        if not SHA.fullmatch(sha):
            raise ProvenanceError(f"invalid commit SHA: {sha}")
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        committer = commit.get("committer") or {}
        forge_author = item.get("author") or {}
        forge_committer = item.get("committer") or {}
        verification = commit.get("verification") or {}
        signer = verification.get("signer") or {}
        if not all(isinstance(value, dict) for value in (commit, author, committer, forge_author, forge_committer, verification, signer)):
            raise ProvenanceError(f"commit {sha} has malformed identity fields")
        message = _bounded(commit.get("message", ""), "commit message", maximum=256 * 1024)
        fields = (
            repository_id,
            sha,
            _one_line(author.get("name", ""), "commit author name", maximum=200),
            _one_line(author.get("email", ""), "commit author email", maximum=254),
            _one_line(committer.get("name", ""), "commit committer name", maximum=200),
            _one_line(committer.get("email", ""), "commit committer email", maximum=254),
            _one_line(forge_author.get("login", ""), "Forgejo commit author", maximum=100),
            _one_line(forge_committer.get("login", ""), "Forgejo commit committer", maximum=100),
            int(verification.get("verified") is True),
            _one_line(verification.get("reason", ""), "signature reason", maximum=200),
            _one_line(signer.get("login", ""), "signature signer", maximum=100),
            _one_line(author.get("date", ""), "authored_at", maximum=50),
            _one_line(committer.get("date", ""), "committed_at", maximum=50),
        )
        self.db.execute(
            """
            INSERT INTO commits(
                repository_id, sha, author_name, author_email, committer_name,
                committer_email, forgejo_author_login, forgejo_committer_login,
                signature_verified, signature_reason, signer_login, authored_at, committed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repository_id, sha) DO UPDATE SET
                author_name=excluded.author_name, author_email=excluded.author_email,
                committer_name=excluded.committer_name, committer_email=excluded.committer_email,
                forgejo_author_login=excluded.forgejo_author_login,
                forgejo_committer_login=excluded.forgejo_committer_login,
                signature_verified=excluded.signature_verified,
                signature_reason=excluded.signature_reason,
                signer_login=excluded.signer_login, authored_at=excluded.authored_at,
                committed_at=excluded.committed_at
            """,
            fields,
        )
        self.db.execute(
            "INSERT INTO pull_request_commits(repository_id, pull_number, sha, position) VALUES (?, ?, ?, ?)",
            (repository_id, pull_number, sha, position),
        )
        self.db.execute("DELETE FROM commit_coauthors WHERE repository_id=? AND sha=?", (repository_id, sha))
        for match in CO_AUTHOR.finditer(message):
            self.db.execute(
                "INSERT OR IGNORE INTO commit_coauthors(repository_id, sha, name, email) VALUES (?, ?, ?, ?)",
                (
                    repository_id,
                    sha,
                    _one_line(match.group("name").strip(), "coauthor name", maximum=200, allow_empty=False),
                    _one_line(match.group("email"), "coauthor email", maximum=254, allow_empty=False),
                ),
            )

    def _insert_review(self, repository_id: int, pull_number: int, item: dict[str, Any]) -> None:
        review_id = item.get("id")
        actor = item.get("user") or {}
        if not isinstance(actor, dict):
            raise ProvenanceError("review has malformed identity")
        review_id = _positive_integer(review_id, "review id")
        self.db.execute(
            "INSERT INTO reviews(repository_id, pull_number, review_id, actor_login, state, submitted_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                repository_id,
                pull_number,
                review_id,
                _one_line(actor.get("login", ""), "review actor", maximum=100),
                _one_line(item.get("state", ""), "review state", maximum=50),
                _one_line(item.get("submitted_at", ""), "review submitted_at", maximum=50),
            ),
        )

    def _insert_comment(self, repository_id: int, pull_number: int, item: dict[str, Any]) -> None:
        comment_id = item.get("id")
        actor = item.get("user") or {}
        if not isinstance(actor, dict):
            raise ProvenanceError("comment has malformed identity")
        comment_id = _positive_integer(comment_id, "comment id")
        self.db.execute(
            "INSERT INTO issue_comments(repository_id, pull_number, comment_id, actor_login, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                repository_id,
                pull_number,
                comment_id,
                _one_line(actor.get("login", ""), "comment actor", maximum=100),
                _one_line(item.get("created_at", ""), "comment created_at", maximum=50),
                _one_line(item.get("updated_at", ""), "comment updated_at", maximum=50),
            ),
        )

    def attest(
        self,
        forgejo_url: str,
        repository: str,
        pull_number: int,
        agent_id: str,
        source: str,
        evidence_ref: str,
        attested_by: str,
    ) -> bool:
        if source not in {"owner-attestation", "session-evidence"}:
            raise ProvenanceError("attestation source must be owner-attestation or session-evidence")
        evidence_ref = _one_line(evidence_ref, "evidence_ref", maximum=500, allow_empty=False)
        attested_by = _one_line(attested_by, "attested_by", maximum=100, allow_empty=False)
        repository_id = self.repository_id(forgejo_url, repository, create=False)
        if self.db.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone() is None:
            raise ProvenanceError(f"unknown agent: {agent_id}")
        if self.db.execute(
            "SELECT 1 FROM pull_requests WHERE repository_id=? AND number=?", (repository_id, pull_number)
        ).fetchone() is None:
            raise ProvenanceError(f"pull request is not indexed: {repository}#{pull_number}")
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO attestations(repository_id, pull_number, agent_id, source, evidence_ref, attested_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (repository_id, pull_number, agent_id, source, evidence_ref, attested_by, _now()),
            )
        return cursor.rowcount == 1

    def _mapped(self, kind: str, values: Sequence[str]) -> dict[str, list[str]]:
        mapped: dict[str, list[str]] = {}
        for value in sorted({item for item in values if item}):
            row = self.db.execute(
                "SELECT agent_id FROM agent_identifiers WHERE kind=? AND value=?", (kind, value)
            ).fetchone()
            if row is not None:
                mapped.setdefault(str(row["agent_id"]), []).append(f"{kind}:{value}")
        return mapped

    def attribution(self, forgejo_url: str, repository: str, pull_number: int) -> Attribution:
        repository_id = self.repository_id(forgejo_url, repository, create=False)
        pull = self.db.execute(
            "SELECT * FROM pull_requests WHERE repository_id=? AND number=?", (repository_id, pull_number)
        ).fetchone()
        if pull is None:
            raise ProvenanceError(f"pull request is not indexed: {repository}#{pull_number}")
        attestations = self.db.execute(
            "SELECT agent_id, source, evidence_ref, attested_by FROM attestations "
            "WHERE repository_id=? AND pull_number=? ORDER BY id",
            (repository_id, pull_number),
        ).fetchall()
        if attestations:
            agent_ids = tuple(sorted({str(row["agent_id"]) for row in attestations}))
            evidence = tuple(
                f"{row['source']}:{row['evidence_ref']} (by {row['attested_by']})" for row in attestations
            )
            return Attribution(
                "attributed" if len(agent_ids) == 1 else "conflict",
                agent_ids,
                "owner-or-session-evidence" if len(agent_ids) == 1 else "conflicting",
                tuple(sorted({str(row["source"]) for row in attestations})),
                evidence,
            )

        commits = self.db.execute(
            "SELECT c.* FROM commits c JOIN pull_request_commits pc "
            "ON c.repository_id=pc.repository_id AND c.sha=pc.sha "
            "WHERE pc.repository_id=? AND pc.pull_number=? ORDER BY pc.position",
            (repository_id, pull_number),
        ).fetchall()
        pull_actor = self._mapped("forgejo_login", [str(pull["author_login"])])
        commit_logins = [str(row["forgejo_author_login"]) for row in commits]
        commit_logins.extend(str(row["forgejo_committer_login"]) for row in commits)
        commit_logins.extend(str(row["signer_login"]) for row in commits if row["signature_verified"])
        commit_actors = self._mapped("forgejo_login", commit_logins)
        exact_agents = tuple(sorted(set(pull_actor) | set(commit_actors)))
        if pull_actor:
            evidence_by_agent = {
                agent: sorted(set(pull_actor.get(agent, ())) | set(commit_actors.get(agent, ())))
                for agent in exact_agents
            }
            evidence = tuple(item for agent in exact_agents for item in evidence_by_agent[agent])
            return Attribution(
                "attributed" if len(exact_agents) == 1 else "conflict",
                exact_agents,
                "exact-forgejo-actor" if len(exact_agents) == 1 else "conflicting",
                ("forgejo-actor",),
                evidence,
            )
        if commit_actors:
            evidence = tuple(item for agent in exact_agents for item in commit_actors[agent])
            return Attribution(
                "partial",
                exact_agents,
                "partial-forgejo-actor",
                ("forgejo-participant",),
                (f"observed-pr-author:{pull['author_login']}", *evidence),
            )

        emails = [str(row["author_email"]) for row in commits]
        emails.extend(str(row["committer_email"]) for row in commits)
        mapped_email = self._mapped("git_email", emails)
        if mapped_email:
            agents = tuple(sorted(mapped_email))
            evidence = tuple(item for agent in agents for item in mapped_email[agent])
            return Attribution(
                "attributed" if len(agents) == 1 else "conflict",
                agents,
                "git-email-unverified" if len(agents) == 1 else "conflicting",
                ("git-identity",),
                evidence,
            )

        coauthors = self.db.execute(
            "SELECT DISTINCT cc.name, cc.email FROM commit_coauthors cc "
            "JOIN pull_request_commits pc ON cc.repository_id=pc.repository_id AND cc.sha=pc.sha "
            "WHERE pc.repository_id=? AND pc.pull_number=? ORDER BY cc.email",
            (repository_id, pull_number),
        ).fetchall()
        declared = tuple(f"Co-Authored-By: {row['name']} <{row['email']}>" for row in coauthors)
        return Attribution("unknown", (), "none", ("declared-coauthor",) if declared else (), declared)

    def pull_summary(self, forgejo_url: str, repository: str, pull_number: int) -> dict[str, Any]:
        repository_id = self.repository_id(forgejo_url, repository, create=False)
        pull = self.db.execute(
            "SELECT * FROM pull_requests WHERE repository_id=? AND number=?", (repository_id, pull_number)
        ).fetchone()
        if pull is None:
            raise ProvenanceError(f"pull request is not indexed: {repository}#{pull_number}")
        commits = self.db.execute(
            "SELECT c.* FROM commits c JOIN pull_request_commits pc "
            "ON c.repository_id=pc.repository_id AND c.sha=pc.sha "
            "WHERE pc.repository_id=? AND pc.pull_number=? ORDER BY pc.position",
            (repository_id, pull_number),
        ).fetchall()
        coauthors = self.db.execute(
            "SELECT cc.sha, cc.name, cc.email FROM commit_coauthors cc "
            "JOIN pull_request_commits pc ON cc.repository_id=pc.repository_id AND cc.sha=pc.sha "
            "WHERE pc.repository_id=? AND pc.pull_number=? ORDER BY pc.position, cc.email",
            (repository_id, pull_number),
        ).fetchall()
        reviews = self.db.execute(
            "SELECT actor_login, state, submitted_at FROM reviews WHERE repository_id=? AND pull_number=? ORDER BY review_id",
            (repository_id, pull_number),
        ).fetchall()
        comments = self.db.execute(
            "SELECT actor_login, created_at FROM issue_comments WHERE repository_id=? AND pull_number=? ORDER BY comment_id",
            (repository_id, pull_number),
        ).fetchall()
        attribution = self.attribution(forgejo_url, repository, pull_number)
        return {
            "repository": repository,
            "pull_number": pull_number,
            "title": pull["title"],
            "state": pull["state"],
            "merged": bool(pull["merged"]),
            "observed": {
                "submitted_by": pull["author_login"],
                "merged_by": pull["merged_by_login"],
                "head_sha": pull["head_sha"],
                "base_sha": pull["base_sha"],
                "synced_at": pull["synced_at"],
            },
            "attribution": {
                "status": attribution.status,
                "agent_ids": list(attribution.agent_ids),
                "confidence": attribution.confidence,
                "sources": list(attribution.sources),
                "evidence": list(attribution.evidence),
            },
            "commits": [
                {
                    "sha": row["sha"],
                    "author_name": row["author_name"],
                    "author_email": row["author_email"],
                    "forgejo_author": row["forgejo_author_login"],
                    "signature_verified": bool(row["signature_verified"]),
                    "signature_reason": row["signature_reason"],
                    "signer": row["signer_login"],
                }
                for row in commits
            ],
            "declared_coauthors": [dict(row) for row in coauthors],
            "reviews": [dict(row) for row in reviews],
            "comment_actors": [dict(row) for row in comments],
        }

    def list_by_agent(self, agent_id: str, repository: str | None = None) -> list[dict[str, Any]]:
        if self.db.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone() is None:
            raise ProvenanceError(f"unknown agent: {agent_id}")
        clauses = []
        parameters: list[Any] = []
        if repository is not None:
            if not REPOSITORY.fullmatch(repository):
                raise ProvenanceError("repository must be owner/name")
            clauses.append("r.full_name=?")
            parameters.append(repository)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.execute(
            "SELECT r.forgejo_url, r.full_name, p.number FROM pull_requests p "
            "JOIN repositories r ON r.id=p.repository_id" + where + " ORDER BY r.full_name, p.number",
            parameters,
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            attribution = self.attribution(row["forgejo_url"], row["full_name"], int(row["number"]))
            if attribution.status == "attributed" and attribution.agent_ids == (agent_id,):
                result.append(self.pull_summary(row["forgejo_url"], row["full_name"], int(row["number"])))
        return result

    def agent_rows(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT a.agent_id, a.display_name, i.kind, i.value, i.source "
            "FROM agents a LEFT JOIN agent_identifiers i ON i.agent_id=a.agent_id "
            "ORDER BY a.agent_id, i.kind, i.value"
        ).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(
                str(row["agent_id"]),
                {"agent_id": row["agent_id"], "display_name": row["display_name"], "identifiers": []},
            )
            if row["kind"] is not None:
                item["identifiers"].append({"kind": row["kind"], "value": row["value"], "source": row["source"]})
        return list(grouped.values())
