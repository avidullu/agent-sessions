"""First-run setup never requires a source checkout or overwrites configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_sessions.cli import main
from agent_sessions.config import load_config
from agent_sessions.onboarding import initialize_archive


def test_init_and_existing_configuration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "workspace with spaces"
    assert main(["--repo-root", str(root), "init"]) == 0
    assert "agentSessionRouter.outputDir" in capsys.readouterr().out
    config = load_config(root)
    assert config.archive_dir == root / "archive"
    assert not config.track_artifacts
    assert (root / "archive/.gitignore").read_text().endswith("*\n")
    before = (root / "sources.toml").read_bytes()
    with pytest.raises(SystemExit, match="already exists"):
        initialize_archive(root)
    assert (root / "sources.toml").read_bytes() == before
    if os.name != "nt":
        assert (root / "sources.toml").stat().st_mode & 0o777 == 0o600


def test_custom_archive_and_existing_ignore(tmp_path: Path) -> None:
    archive = tmp_path / 'external "quoted"' if os.name != "nt" else tmp_path / "external archive"
    archive.mkdir()
    (archive / ".gitignore").write_text("existing policy\n")
    root = tmp_path
    initialize_archive(root, archive)
    assert load_config(root).archive_dir == archive
    assert (archive / ".gitignore").read_text() == "existing policy\n"


def test_relative_archive(tmp_path: Path) -> None:
    initialize_archive(tmp_path, Path("custom"))
    assert load_config(tmp_path).archive_dir == tmp_path / "custom"


def test_unicode_workspace(tmp_path: Path) -> None:
    root = tmp_path / "archive-\U0001f4da"
    initialize_archive(root)
    assert load_config(root).archive_dir == root / "archive"


def test_external_archive_rejected_before_writes(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="direct child"):
        initialize_archive(tmp_path / "workspace", tmp_path / "external")
    assert not (tmp_path / "workspace").exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink privilege is not assumed")
def test_ignore_symlink_not_followed(tmp_path: Path) -> None:
    policy = tmp_path / "policy"
    policy.write_text("preserve")
    (tmp_path / ".gitignore").symlink_to(policy)
    with pytest.raises(SystemExit, match="symlink"):
        initialize_archive(tmp_path)
    assert policy.read_text() == "preserve"


@pytest.mark.parametrize("directory", [".", "raw"])
def test_reject_overlapping_layout(tmp_path: Path, directory: str) -> None:
    with pytest.raises(SystemExit, match="separate"):
        initialize_archive(tmp_path, Path(directory))
    assert not (tmp_path / "sources.toml").exists()


def test_missing_config_actionable_and_explicit_path_not_ignored(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="init"):
        main(["--repo-root", str(tmp_path), "discover"])
    initialize_archive(tmp_path)
    with pytest.raises(SystemExit, match="Configuration not found"):
        load_config(tmp_path, Path("typo.toml"))


def test_bad_toml_and_init_config_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "sources.toml").write_text("secret-value = [invalid")
    assert main(["--repo-root", str(tmp_path), "status"]) == 2
    error = capsys.readouterr().err
    assert "TOMLDecodeError" in error and "secret-value" not in error
    with pytest.raises(SystemExit):
        main(["--config", "custom.toml", "init"])


def test_init_filesystem_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "file"
    target.write_text("preserve")
    assert main(["--repo-root", str(target), "init"]) == 2
    assert "Setup failed" in capsys.readouterr().err
    assert target.read_text() == "preserve"
