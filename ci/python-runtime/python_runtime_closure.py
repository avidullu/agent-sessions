#!/usr/bin/env python3
"""Admit a pinned Python distribution with BheemCI; consume it without network access."""

import argparse
import hashlib
import json
import os
import platform
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

PROFILE = "forge-service.python-runtime-profile.v1"
LOCK = "forge-service.python-runtime-lock.v1"
HEX = re.compile(r"[0-9a-f]{64}")
FILES = {"profile.json", "python.tar.gz", "bheemci"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    require(path.stat().st_size <= 1024 * 1024, "metadata too large")
    return json.loads(path.read_text(encoding="utf-8"))


def profile(path):
    value = read_json(path)
    require(
        set(value)
        == {"schema", "python_version", "platform", "source_url", "archive_sha256"},
        "profile fields",
    )
    require(
        value["schema"] == PROFILE and value["platform"] == "linux-x86_64",
        "unsupported profile",
    )
    require(
        re.fullmatch(r"3\.13\.\d+", value["python_version"]),
        "unsupported Python version",
    )
    require(HEX.fullmatch(value["archive_sha256"]), "invalid archive digest")
    require(
        re.fullmatch(
            r"https://github\.com/astral-sh/python-build-standalone/releases/download/\d{8}/"
            r"cpython-"
            + re.escape(value["python_version"])
            + r"%2B\d{8}-x86_64-unknown-linux-gnu-install_only_stripped\.tar\.gz",
            value["source_url"],
        ),
        "unsupported upstream",
    )
    return value


def bheem(binary, *args):
    result = subprocess.run(
        [str(binary), "closure", *map(str, args)], capture_output=True, timeout=600
    )
    require(result.returncode == 0, "BheemCI command refused (output withheld)")
    return json.loads(result.stdout)


def readonly_file(path):
    mode = path.lstat().st_mode
    require(stat.S_ISREG(mode) and not mode & 0o222, "mutable or redirected file")


def verify(root, lock_path, profile_path):
    expected = profile(profile_path)
    lock = read_json(lock_path)
    require(
        set(lock) == {"schema", "closure_digest", "verifier_sha256", "profile_sha256"},
        "lock fields",
    )
    require(lock["schema"] == LOCK, "lock schema")
    for key in ("closure_digest", "verifier_sha256", "profile_sha256"):
        require(isinstance(lock[key], str) and HEX.fullmatch(lock[key]), "lock digest")
    require(sha(profile_path) == lock["profile_sha256"], "unpromoted profile")
    snapshot = root / "snapshots" / lock["closure_digest"]
    for directory in (root / "snapshots", snapshot, snapshot / "work"):
        require(
            not directory.is_symlink() and directory.is_dir(),
            "missing or redirected snapshot",
        )
    for directory in (snapshot, snapshot / "work"):
        require(not directory.stat().st_mode & 0o222, "mutable snapshot")
    require(
        {p.name for p in snapshot.iterdir()} == {"closure.json", "work"},
        "unexpected snapshot entries",
    )
    require(
        {p.name for p in (snapshot / "work").iterdir()} == FILES,
        "unexpected payload entries",
    )
    for name in FILES:
        readonly_file(snapshot / "work" / name)
    binary = snapshot / "work/bheemci"
    require(sha(binary) == lock["verifier_sha256"], "verifier digest mismatch")
    manifest = snapshot / "closure.json"
    readonly_file(manifest)
    require(
        bheem(binary, "digest", "--closure", manifest).get("closure_digest")
        == "sha256:" + lock["closure_digest"],
        "closure identity mismatch",
    )
    require(
        bheem(binary, "admit", "--store", root / "store", "--closure", manifest).get(
            "admitted"
        )
        is True,
        "closure admission failed",
    )
    entries = read_json(manifest)["entries"]
    require(
        len(entries) == len(FILES) and {entry["path"] for entry in entries} == FILES,
        "manifest inventory",
    )
    for entry in entries:
        target = snapshot / "work" / entry["path"]
        require(
            entry["size_bytes"] == target.stat().st_size
            and entry["digest"] == "sha256:" + sha(target),
            "projection mismatch",
        )
        require(
            entry["executable"] == (entry["path"] == "bheemci")
            and bool(target.stat().st_mode & 0o111) == entry["executable"],
            "projection mode mismatch",
        )
    require(read_json(snapshot / "work/profile.json") == expected, "profile mismatch")
    require(
        sha(snapshot / "work/python.tar.gz") == expected["archive_sha256"],
        "upstream archive mismatch",
    )
    return snapshot / "work/python.tar.gz"


def unpack(archive, into):
    """Only an admitted archive may reach here. Enforce containment and expansion bounds too."""
    require(not into.exists() and not into.is_symlink(), "destination already exists")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        require(
            len(members) <= 50000 and sum(m.size for m in members) <= 1024**3,
            "archive exceeds bounds",
        )
        for member in members:
            parts = PurePosixPath(member.name).parts
            require(
                parts
                and parts[0] == "python"
                and ".." not in parts
                and not member.name.startswith("/"),
                "archive path escape",
            )
            require(
                member.isfile() or member.isdir() or member.issym(),
                "unsupported archive entry",
            )
            require(not member.mode & 0o7000, "privileged archive mode")
            if member.issym():
                target = posixpath.normpath(
                    posixpath.join(posixpath.dirname(member.name), member.linkname)
                )
                require(
                    not member.linkname.startswith("/")
                    and target.startswith("python/"),
                    "archive link escape",
                )
        # Python 3.12+ data_filter checks link targets and forbids devices/escapes.
        # Never fall back to unfiltered extraction on an older bootstrap interpreter.
        into.mkdir(mode=0o700)
        bundle.extractall(into, members=members, filter="data")
    return into / "python/bin/python3"


def install(root, lock_path, profile_path, into):
    require(
        platform.system() == "Linux" and platform.machine() in {"x86_64", "amd64"},
        "unsupported host",
    )
    archive = verify(root, lock_path, profile_path)
    python = unpack(archive, into)
    result = subprocess.run(
        [str(python), "-I", "-c", "import platform; print(platform.python_version())"],
        capture_output=True,
        timeout=30,
    )
    require(
        result.returncode == 0
        and result.stdout.decode().strip() == profile(profile_path)["python_version"],
        "runtime version mismatch",
    )
    return python


def snapshot(binary, payload, root, manifest):
    root.mkdir(parents=True, exist_ok=True)
    bheem(
        binary,
        "add-tree",
        "--store",
        root / "store",
        "--dir",
        payload,
        "--role",
        "tool",
        "--closure",
        manifest,
        "--closure-name",
        "python-runtime-v1",
    )
    digest = bheem(binary, "digest", "--closure", manifest)[
        "closure_digest"
    ].removeprefix("sha256:")
    snapshots = root / "snapshots"
    snapshots.mkdir(exist_ok=True)
    target = snapshots / digest
    if not target.exists():
        stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=snapshots))
        bheem(
            binary,
            "materialize",
            "--store",
            root / "store",
            "--closure",
            manifest,
            "--into",
            stage / "work",
        )
        shutil.copyfile(manifest, stage / "closure.json")
        for current, _dirs, files in os.walk(stage, topdown=False):
            for name in files:
                item = Path(current) / name
                item.chmod(0o555 if name == "bheemci" else 0o444)
            Path(current).chmod(0o555)
        os.rename(stage, target)
    return digest


def curate(args):
    expected = profile(args.profile)
    require(
        sha(args.archive_file) == expected["archive_sha256"], "download digest mismatch"
    )
    root, archive = args.root.resolve(), args.archive.resolve()
    require(
        root != archive and root not in archive.parents and archive not in root.parents,
        "overlapping stores",
    )
    require(not args.lock_output.exists(), "lock output already exists")
    import fcntl

    root.mkdir(parents=True, exist_ok=True)
    with (root / ".curation.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix="python-curation-") as temporary:
            temp = Path(temporary)
            payload = temp / "payload"
            payload.mkdir()
            shutil.copyfile(args.profile, payload / "profile.json")
            shutil.copyfile(args.archive_file, payload / "python.tar.gz")
            shutil.copyfile(args.bheemci, payload / "bheemci")
            (payload / "bheemci").chmod(0o755)
            digest = snapshot(args.bheemci, payload, root, temp / "closure.json")
            require(
                snapshot(args.bheemci, payload, archive, temp / "archive.json")
                == digest,
                "archive identity mismatch",
            )
            candidate = temp / "lock.json"
            candidate.write_text(
                json.dumps(
                    {
                        "schema": LOCK,
                        "closure_digest": digest,
                        "verifier_sha256": sha(args.bheemci),
                        "profile_sha256": sha(args.profile),
                    },
                    indent=2,
                )
                + "\n"
            )
            verify(root, candidate, args.profile)
            verify(archive, candidate, args.profile)
            bheem(
                args.bheemci,
                "materialize",
                "--store",
                archive / "store",
                "--closure",
                archive / "snapshots" / digest / "closure.json",
                "--into",
                temp / "restored",
            )
            for name in FILES:
                require(
                    sha(payload / name) == sha(temp / "restored" / name),
                    "archive restore mismatch",
                )
            install(root, candidate, args.profile, temp / "probe")
            # Candidate preparation only: no global current pointer or live runner changes.
            with args.lock_output.open("x", encoding="utf-8") as stream:
                stream.write(candidate.read_text())
            print(
                json.dumps(
                    {
                        "closure_digest": digest,
                        "archive_restore": "verified",
                        "activated": False,
                    }
                )
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("curate")
    for name in (
        "root",
        "archive",
        "profile",
        "archive-file",
        "bheemci",
        "lock-output",
    ):
        build.add_argument("--" + name, type=Path, required=True)
    for action in ("verify", "install"):
        check = sub.add_parser(action)
        for name in ("root", "lock", "profile"):
            check.add_argument("--" + name, type=Path, required=True)
        if action == "install":
            check.add_argument("--into", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "curate":
            curate(args)
        elif args.action == "verify":
            print(verify(args.root, args.lock, args.profile))
        else:
            print(install(args.root, args.lock, args.profile, args.into))
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        tarfile.TarError,
    ) as error:
        parser.exit(1, "Python closure refused: " + type(error).__name__ + "\n")


if __name__ == "__main__":
    main()
