"""Local SQLite index for Forgejo pull-request and coding-agent provenance.

The database stores bounded source-control metadata and evidence references. It
never stores API tokens, pull-request bodies, comments, or session transcripts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol

SCHEMA_VERSION = 1
DEFAULT_DATABASE = Path("~/.local/share/agent-sessions/forgejo-provenance.sqlite3").expanduser()
MAX_API_BYTES = 8 * 1024 * 1024
MAX_POLICY_BYTES = 256 * 1024
MAX_TEXT = 1000
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
AGENT_ID = re.compile(r"[a-z][a-z0-9-]{1,38}[a-z0-9]\Z")
SHA = re.compile(r"[0-9a-f]{40,64}\Z")
CO_AUTHOR = re.compile(
    r"^Co-Authored-By:\s*(?P<name>[^<\r\n]{1,200}?)\s*<(?P<email>[^<>\s]{3,254})>\s*$",
    re.IGNORECASE | re.MULTILINE,
)
WINDOWS_ACL_PROBE = """
$ErrorActionPreference = 'Stop'
$acl = Get-Acl -LiteralPath $env:AGENT_SESSIONS_PRIVATE_PATH
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$owner = ([System.Security.Principal.NTAccount]$acl.Owner).Translate(
    [System.Security.Principal.SecurityIdentifier]
).Value
$ownerCandidates = @(
    $current,
    'S-1-5-18',
    'S-1-5-32-544'
)
if ($ownerCandidates -notcontains $owner) {
    exit 4
}
$trusted = $ownerCandidates + @('S-1-3-0', 'S-1-3-4')
$unexpected = @()
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) {
        continue
    }
    $sid = $rule.IdentityReference.Translate(
        [System.Security.Principal.SecurityIdentifier]
    ).Value
    if ($trusted -notcontains $sid) {
        $unexpected += $sid
    }
}
if ($unexpected.Count -ne 0) {
    exit 3
}
"""


class ProvenanceError(RuntimeError):
    """A database, policy, API, or attribution invariant failed."""


def _fail(message: str) -> NoReturn:
    raise ProvenanceError(message)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bounded(value: Any, field: str, *, maximum: int = MAX_TEXT, allow_empty: bool = True) -> str:
    if value is None and allow_empty:
        return ""
    if not isinstance(value, str) or "\0" in value or len(value) > maximum:
        raise ProvenanceError(f"{field} must be a string of at most {maximum} characters")
    if not allow_empty and not value.strip():
        raise ProvenanceError(f"{field} must not be empty")
    return value


def _one_line(value: Any, field: str, *, maximum: int = MAX_TEXT, allow_empty: bool = True) -> str:
    result = _bounded(value, field, maximum=maximum, allow_empty=allow_empty)
    if "\n" in result or "\r" in result:
        raise ProvenanceError(f"{field} must be one line")
    return result


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ProvenanceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _json(raw: bytes, description: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_pairs,
            parse_constant=lambda token: _fail(f"non-finite JSON value in {description}: {token}"),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"invalid JSON in {description}: {exc}") from exc


def _read_regular(path: Path, *, maximum: int, secret: bool = False) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ProvenanceError(f"cannot stat {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProvenanceError(f"expected a regular non-symlink file: {path}")
    if info.st_size > maximum:
        raise ProvenanceError(f"file exceeds {maximum} bytes: {path}")
    if secret:
        _require_private_access(path, info)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ProvenanceError(f"cannot read {path}: {exc}") from exc


def _require_private_access(path: Path, info: os.stat_result | None = None) -> None:
    """Require POSIX owner-only bits or a Windows ACL without broad readers."""
    observed = info if info is not None else path.lstat()
    if os.name != "nt":
        if stat.S_IMODE(observed.st_mode) & 0o077:
            raise ProvenanceError(f"secret file must not be group/world accessible: {path}")
        return
    environment = os.environ.copy()
    environment["AGENT_SESSIONS_PRIVATE_PATH"] = str(path)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", _powershell_encoded(WINDOWS_ACL_PROBE)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProvenanceError(f"cannot verify the current-user Windows ACL: {path}") from exc
    if result.returncode != 0:
        raise ProvenanceError(f"secret file ACL grants an unexpected Windows principal: {path}")


def _powershell_encoded(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


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
        self.path.parent.chmod(0o700)
        _require_private_access(self.path.parent)
        if self.path.exists():
            info = self.path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise ProvenanceError(f"database must be a regular non-symlink file: {self.path}")
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA secure_delete = ON")
        self.path.chmod(0o600)
        _require_private_access(self.path)
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in {0, SCHEMA_VERSION}:
            connection.close()
            raise ProvenanceError(f"unsupported provenance schema version {version}")
        if version == 0:
            self._create_schema(connection)
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
        rows = 0
        with self.db:
            for index, principal in enumerate(principals):
                if not isinstance(principal, dict):
                    raise ProvenanceError(f"identity policy principal {index} is not an object")
                agent_id = _one_line(principal.get("id"), f"principal {index} id", allow_empty=False)
                if not AGENT_ID.fullmatch(agent_id) or principal.get("kind") != "coding-agent":
                    continue
                display = _one_line(principal.get("display_name"), f"principal {agent_id} display_name", allow_empty=False)
                username = _one_line(principal.get("username"), f"principal {agent_id} username", allow_empty=False)
                email = _one_line(principal.get("email"), f"principal {agent_id} email", allow_empty=False)
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
                rows += 1
        return rows

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
        number = value.get("number")
        if not isinstance(number, int) or number <= 0:
            raise ProvenanceError("pull request number must be positive")
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
        if not isinstance(review_id, int) or not isinstance(actor, dict):
            raise ProvenanceError("review has malformed identity")
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
        if not isinstance(comment_id, int) or not isinstance(actor, dict):
            raise ProvenanceError("comment has malformed identity")
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
        exact_logins = [str(pull["author_login"])]
        exact_logins.extend(str(row["forgejo_author_login"]) for row in commits)
        exact_logins.extend(str(row["forgejo_committer_login"]) for row in commits)
        exact_logins.extend(str(row["signer_login"]) for row in commits if row["signature_verified"])
        exact = self._mapped("forgejo_login", exact_logins)
        if exact:
            agents = tuple(sorted(exact))
            evidence = tuple(item for agent in agents for item in exact[agent])
            return Attribution(
                "attributed" if len(agents) == 1 else "conflict",
                agents,
                "exact-forgejo-actor" if len(agents) == 1 else "conflicting",
                ("forgejo-actor",),
                evidence,
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


class ForgejoClient:
    def __init__(self, base_url: str, token_file: Path):
        self.base_url = base_url.rstrip("/")
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path:
            raise ProvenanceError("Forgejo URL must be one HTTPS origin")
        token = _read_regular(token_file.expanduser(), maximum=4096, secret=True).decode("utf-8").strip()
        if not token or any(character.isspace() for character in token):
            raise ProvenanceError("Forgejo token is empty or malformed")
        self._token = token

    def get(self, path: str) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}/api/v1{path}",
            headers={"Accept": "application/json", "Authorization": f"token {self._token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(MAX_API_BYTES + 1)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                value = _json(exc.read(MAX_API_BYTES + 1), f"Forgejo error {exc.code}")
                if isinstance(value, dict):
                    detail = _one_line(value.get("message", ""), "Forgejo error", maximum=300)
            except ProvenanceError:
                pass
            raise ProvenanceError(f"Forgejo GET {path} returned {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProvenanceError(f"Forgejo GET {path} failed: {exc}") from exc
        if len(raw) > MAX_API_BYTES:
            raise ProvenanceError(f"Forgejo GET {path} exceeded {MAX_API_BYTES} bytes")
        return _json(raw, f"Forgejo GET {path}")

    def pages(self, path: str, *, limit: int = 50, max_pages: int = 100) -> list[Any]:
        values: list[Any] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            batch = self.get(f"{path}{separator}page={page}&limit={limit}")
            if not isinstance(batch, list):
                raise ProvenanceError(f"Forgejo paginated response for {path} is not an array")
            values.extend(batch)
            if len(batch) < limit:
                return values
        raise ProvenanceError(f"Forgejo pagination for {path} exceeded {max_pages} pages")


class ForgejoSource(Protocol):
    """The read-only client surface used by repository synchronization."""

    base_url: str

    def get(self, path: str) -> Any: ...

    def pages(self, path: str) -> list[Any]: ...


def _repo_path(repository: str) -> str:
    if not REPOSITORY.fullmatch(repository):
        raise ProvenanceError("repository must be owner/name")
    owner, name = repository.split("/", 1)
    return f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}"


def sync_repository(
    store: Store,
    client: ForgejoSource,
    repository: str,
    pull_numbers: Sequence[int] = (),
    *,
    max_pulls: int = 500,
) -> int:
    root = _repo_path(repository)
    started = _now()
    with store.db:
        repository_id = store.repository_id(client.base_url, repository, create=True)
    count = 0
    try:
        if pull_numbers:
            if len(set(pull_numbers)) != len(pull_numbers) or any(number <= 0 for number in pull_numbers):
                raise ProvenanceError("pull numbers must be unique positive integers")
            pulls = [client.get(f"{root}/pulls/{number}") for number in pull_numbers]
        else:
            pulls = client.pages(f"{root}/pulls?state=all&sort=recentupdate")
            if len(pulls) > max_pulls:
                raise ProvenanceError(f"repository has {len(pulls)} pulls, above --max-pulls={max_pulls}")
        with store.db:
            for value in pulls:
                if not isinstance(value, dict):
                    raise ProvenanceError("pull response contains a non-object")
                number = store.upsert_pull(client.base_url, repository, value)
                commits = client.pages(f"{root}/pulls/{number}/commits")
                reviews = client.pages(f"{root}/pulls/{number}/reviews")
                comments = client.pages(f"{root}/issues/{number}/comments")
                if not all(isinstance(item, dict) for item in (*commits, *reviews, *comments)):
                    raise ProvenanceError(f"pull request {number} details contain a non-object")
                store.replace_pull_details(client.base_url, repository, number, commits, reviews, comments)
                count += 1
            store.db.execute(
                "INSERT INTO sync_runs(repository_id, started_at, completed_at, pull_count, status, error) "
                "VALUES (?, ?, ?, ?, 'success', '')",
                (repository_id, started, _now(), count),
            )
        return count
    except Exception as exc:
        with store.db:
            store.db.execute(
                "INSERT INTO sync_runs(repository_id, started_at, completed_at, pull_count, status, error) "
                "VALUES (?, ?, ?, ?, 'failed', ?)",
                (repository_id, started, _now(), count, str(exc)[:500]),
            )
        raise


def format_summary(value: dict[str, Any]) -> str:
    attribution = value["attribution"]
    observed = value["observed"]
    agents = ", ".join(attribution["agent_ids"]) if attribution["agent_ids"] else "unknown"
    lines = [
        f"{value['repository']}#{value['pull_number']}: {value['title']}",
        f"Observed: submitted_by={observed['submitted_by'] or '-'} merged_by={observed['merged_by'] or '-'} state={value['state']} merged={str(value['merged']).lower()}",
        f"Agent attribution: {agents} (status={attribution['status']}, confidence={attribution['confidence']})",
    ]
    if attribution["evidence"]:
        lines.append("Evidence:")
        lines.extend(f"- {item}" for item in attribution["evidence"])
    lines.append("Commits:")
    for commit in value["commits"]:
        lines.append(
            f"- {commit['sha'][:12]} author={commit['author_name']} <{commit['author_email']}> "
            f"forgejo={commit['forgejo_author'] or '-'} signed={str(commit['signature_verified']).lower()}"
        )
    if value["declared_coauthors"]:
        lines.append("Declared co-authors (unverified trailers):")
        lines.extend(f"- {item['name']} <{item['email']}>" for item in value["declared_coauthors"])
    if value["reviews"]:
        lines.append("Reviews:")
        lines.extend(f"- {item['actor_login']}: {item['state']}" for item in value["reviews"])
    if value["comment_actors"]:
        actors = sorted({item["actor_login"] for item in value["comment_actors"]})
        lines.append("Comment actors: " + ", ".join(actors))
    return "\n".join(lines)
