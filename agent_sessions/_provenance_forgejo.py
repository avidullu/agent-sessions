"""Read-only Forgejo client and repository synchronization."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, NoReturn, Protocol

from ._provenance_common import (
    ProvenanceError,
    _json,
    _now,
    _one_line,
    _positive_integer,
    _read_regular,
)
from ._provenance_store import REPOSITORY, Store

MAX_API_BYTES = 8 * 1024 * 1024


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward a provenance credential beyond the configured origin."""

    def redirect_request(
        self,
        request: Any,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> NoReturn:
        raise ProvenanceError("Forgejo redirected a provenance request; redirects are forbidden")


class ForgejoClient:
    def __init__(self, base_url: str, token_file: Path):
        self.base_url = base_url.rstrip("/")
        parsed = urllib.parse.urlsplit(self.base_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ProvenanceError("Forgejo URL must be one HTTPS origin without userinfo")
        token = _read_regular(token_file.expanduser(), maximum=4096, secret=True).decode("utf-8").strip()
        if not token or any(character.isspace() for character in token):
            raise ProvenanceError("Forgejo token is empty or malformed")
        self._token = token
        self._opener = urllib.request.build_opener(_RejectRedirects())

    def get(self, path: str) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}/api/v1{path}",
            headers={"Accept": "application/json"},
        )
        request.add_unredirected_header("Authorization", f"token {self._token}")
        try:
            with self._opener.open(request, timeout=30) as response:
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

    def pages(
        self,
        path: str,
        *,
        limit: int = 50,
        max_pages: int = 100,
        maximum: int | None = None,
    ) -> list[Any]:
        if limit < 1 or max_pages < 1 or maximum is not None and maximum < 1:
            raise ProvenanceError("pagination limits must be positive")
        values: list[Any] = []
        separator = "&" if "?" in path else "?"
        page_size = min(limit, maximum + 1) if maximum is not None else limit
        for page in range(1, max_pages + 1):
            batch = self.get(f"{path}{separator}page={page}&limit={page_size}")
            if not isinstance(batch, list):
                raise ProvenanceError(f"Forgejo paginated response for {path} is not an array")
            values.extend(batch)
            if maximum is not None and len(values) > maximum:
                return values[: maximum + 1]
            if len(batch) < page_size:
                return values
        raise ProvenanceError(f"Forgejo pagination for {path} exceeded {max_pages} pages")


class ForgejoSource(Protocol):
    """The read-only client surface used by repository synchronization."""

    base_url: str

    def get(self, path: str) -> Any: ...

    def pages(self, path: str, *, maximum: int | None = None) -> list[Any]: ...


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
    _positive_integer(max_pulls, "max_pulls")
    root = _repo_path(repository)
    started = _now()
    with store.db:
        repository_id = store.repository_id(client.base_url, repository, create=True)
    count = 0
    try:
        pulls: Iterable[Any]
        if pull_numbers:
            if len(set(pull_numbers)) != len(pull_numbers):
                raise ProvenanceError("pull numbers must be unique positive integers")
            checked_numbers = tuple(_positive_integer(number, "pull number") for number in pull_numbers)
            pulls = (client.get(f"{root}/pulls/{number}") for number in checked_numbers)
        else:
            listed_pulls = client.pages(f"{root}/pulls?state=all&sort=recentupdate", maximum=max_pulls)
            if len(listed_pulls) > max_pulls:
                raise ProvenanceError(f"repository has {len(listed_pulls)} pulls, above --max-pulls={max_pulls}")
            pulls = listed_pulls
        for value in pulls:
            if not isinstance(value, dict):
                raise ProvenanceError("pull response contains a non-object")
            number = _positive_integer(value.get("number"), "pull request number")
            commits = client.pages(f"{root}/pulls/{number}/commits")
            reviews = client.pages(f"{root}/pulls/{number}/reviews")
            comments = client.pages(f"{root}/issues/{number}/comments")
            if not all(isinstance(item, dict) for item in (*commits, *reviews, *comments)):
                raise ProvenanceError(f"pull request {number} details contain a non-object")
            with store.db:
                number = store.upsert_pull(client.base_url, repository, value)
                store.replace_pull_details(client.base_url, repository, number, commits, reviews, comments)
            count += 1
        with store.db:
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
