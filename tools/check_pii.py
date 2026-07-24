"""CI gate: no real user home paths or private identifiers in tracked files (L11).

The tracked tree is public; catalogs, docs, and fixtures must never carry a
real user home directory, an encoded Claude project key with a real username,
a tailnet hostname, or a personal email address. The rules are structural
(they match *any* username), so this file needs no private strings of its own:

1. Home-directory paths — native Windows, WSL UNC, POSIX, ``/mnt`` and macOS
   forms, plus the encoded ``X--Users-<user>-...`` / ``-home-<user>-...``
   project-key forms — are flagged unless the username component is an
   approved placeholder (``example-user``, template tokens, and the fake
   users unit tests are allowed to use).
2. Tailnet hostnames (``*.ts.net``) and personal-provider email addresses are
   flagged unconditionally.

Add a new fake username to ``ALLOWED_USERS`` deliberately, in review — that
is the escape hatch for tests and docs, and it must stay an explicit list so
a real username can never drift in silently.

Run: ``python -m tools.check_pii`` (stdlib only; scans ``git ls-files``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Placeholder usernames allowed inside home-path shapes. Lowercase comparison.
ALLOWED_USERS = {
    "example-user",
    "example",
    "<user>",
    "<username>",
    "{user}",
    "{username}",
    "user",
    "runneradmin",  # CI runner homes in captured tool output/docs
    "runner",
    # Fake users the unit tests and contract docs use:
    "alice",
    "bob",
    "carol",
    "other",
    "someone",
    "test",
    "a",
    "u",
    "you",
    "demo",
    "testuser",
    "brew",  # test_portable_paths uses "-home-brew" as a non-path example
    "username",
}

# Files that legitimately discuss the patterns themselves.
EXEMPT_FILES = {
    "tools/check_pii.py",
    "tools/migrate_portable_paths.py",
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".zip"}

_TOKEN = r"[^\\/\s\"'`|)\]}>]+"

HOME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("windows-home", re.compile(rf"[A-Za-z]:[\\/]+Users[\\/]+(?P<user>{_TOKEN})")),
    ("wsl-home", re.compile(rf"[\\/]{{2}}wsl(?:\.localhost|\$)?[\\/][^\\/]+[\\/]home[\\/](?P<user>{_TOKEN})")),
    ("posix-home", re.compile(rf"(?<![\w.])/home/(?P<user>{_TOKEN})")),
    ("macos-home", re.compile(rf"(?<![\w.])/Users/(?P<user>{_TOKEN})")),
    ("mounted-home", re.compile(rf"/mnt/[A-Za-z]/Users/(?P<user>{_TOKEN})")),
    ("encoded-windows-home", re.compile(r"(?<![A-Za-z0-9])[A-Za-z]--Users-(?P<user>[A-Za-z0-9_.]+)")),
    ("encoded-posix-home", re.compile(r"(?<![A-Za-z0-9])-home-(?P<user>[A-Za-z0-9_.]+)")),
)

UNCONDITIONAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("tailnet-hostname", re.compile(r"\b[A-Za-z0-9-]+\.(?:tail[0-9a-f]+\.)?ts\.net\b")),
    (
        "personal-email",
        re.compile(r"\b[A-Za-z0-9_.+-]+@(?:gmail|googlemail|live|hotmail|outlook|yahoo|proton|protonmail)\.[A-Za-z.]+"),
    ),
)


def tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [name for name in output.decode("utf-8", errors="replace").split("\0") if name]


def normalized_user(raw: str) -> str:
    # Strip quoting and placeholder punctuation so `<user>`, `{user}`, "..."
    # and similar documentation forms normalize to a comparable token. An
    # empty result (pure ellipsis/punctuation) is treated as a placeholder.
    return raw.strip().strip("`'\",;:!?*<>{}[]^().").lower()


def scan_line(line: str) -> list[str]:
    problems: list[str] = []
    for label, pattern in HOME_PATTERNS:
        for match in pattern.finditer(line):
            raw_user = match.group("user")
            if "{" in raw_user or "$" in raw_user:
                continue  # format/template interpolation, not a literal username
            user = normalized_user(raw_user)
            if user and user not in ALLOWED_USERS:
                problems.append(f"{label}: {match.group(0)[:80]}")
    for label, pattern in UNCONDITIONAL_PATTERNS:
        for match in pattern.finditer(line):
            problems.append(f"{label}: {match.group(0)[:80]}")
    return problems


def main() -> int:
    failures: list[str] = []
    for name in tracked_files():
        if name in EXEMPT_FILES or Path(name).suffix.lower() in SKIP_SUFFIXES:
            continue
        path = REPO_ROOT / name
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        if b"\0" in blob[:8192]:
            continue  # binary
        text = blob.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for problem in scan_line(line):
                failures.append(f"{name}:{lineno}: {problem}")

    if failures:
        print("check_pii: tracked files carry non-placeholder user paths or private identifiers:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(f"check_pii: {len(failures)} finding(s).", file=sys.stderr)
        return 1
    print("check_pii: OK — no real home paths, tailnet hosts, or personal emails in tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
