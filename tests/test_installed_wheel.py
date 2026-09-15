"""Exercise the distributable, not an editable install (Linux and Windows CI)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_installed_wheel_router_journey(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheels"
    subprocess.run([sys.executable, "-m", "pip", "wheel", str(repo), "--no-deps", "-w", str(wheel_dir)],
                   check=True, capture_output=True, text=True)
    environment = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                    str(next(wheel_dir.glob("*.whl")))], check=True, capture_output=True, text=True)
    command = scripts / ("agent-archive.exe" if os.name == "nt" else "agent-archive")
    workspace = tmp_path / "new user workspace"
    workspace.mkdir()
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(command), *args], cwd=workspace, env=env, capture_output=True, text=True, check=True)

    assert "agentSessionRouter.outputDir" in run("init").stdout
    # Restrict discovery to synthetic evidence, never scan the CI user's agent stores.
    (workspace / "sources.toml").write_text('[archive]\narchive_dir = "archive"\n', encoding="utf-8")
    artifact = workspace / "archive/zai-vscode/example.md"
    artifact.parent.mkdir()
    artifact.write_text("# Fixture\n\n## user\nQuestion\n\n## assistant\nAnswer\n", encoding="utf-8")
    record = {"source": "zai-vscode", "kind": "vscode_chat", "source_file": "fixture.jsonl",
              "sha256": "fixture", "messages": 2, "markdown": "archive/zai-vscode/example.md",
              "metadata": {"session_id": "fixture", "model_provider": "zai"}}
    (workspace / "archive/.router-index.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    run("discover")
    status = json.loads(run("status", "--json").stdout)
    assert status["indexed_records"] == 1
    run("export", "--all")
    assert "Answer" in artifact.read_text(encoding="utf-8")
    assert json.loads(run("status", "--json").stdout)["indexed_records"] == 1
