"""Tests for agent_sessions.baseline_agent."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.baseline_agent import (
    baseline_bundle,
    baseline_schema_contract,
    bullet_list,
    bundle_constraints,
    evidence_record,
    proposal_schema,
    render_agent_prompt,
    select_records,
)
from agent_sessions.config import ArchiveConfig


class TestSelectRecords:
    def test_selects_by_focus(self) -> None:
        records = [
            {
                "source": "s1",
                "kind": "k1",
                "messages": 5,
                "markdown": "a/s1.md",
                "metadata": {},
                "source_file": "/f1",
            },
            {
                "source": "s2",
                "kind": "k2",
                "messages": 3,
                "markdown": "a/s2.md",
                "metadata": {"session_id": "badminton"},
                "source_file": "/f2",
            },
        ]
        result = select_records(records, focus=["badminton"], max_sessions=10)
        assert len(result) == 1
        assert result[0]["source"] == "s2"

    def test_selects_all_when_no_focus(self) -> None:
        records = [
            {
                "source": "s1",
                "kind": "k1",
                "messages": 5,
                "markdown": "a/s1.md",
                "metadata": {},
                "source_file": "/f1",
            },
            {
                "source": "s2",
                "kind": "k2",
                "messages": 3,
                "markdown": "a/s2.md",
                "metadata": {},
                "source_file": "/f2",
            },
        ]
        result = select_records(records, focus=[], max_sessions=10)
        assert len(result) == 2

    def test_respects_max_sessions(self) -> None:
        records = [
            {
                "source": f"s{i}",
                "kind": "k",
                "messages": i,
                "markdown": f"a/s{i}.md",
                "metadata": {},
                "source_file": f"/f{i}",
            }
            for i in range(20)
        ]
        result = select_records(records, focus=[], max_sessions=5)
        assert len(result) <= 5

    def test_sorts_by_focus_score(self) -> None:
        records = [
            {
                "source": "s1",
                "kind": "k",
                "messages": 1,
                "markdown": "a/s1.md",
                "metadata": {},
                "source_file": "/f1",
            },
            {
                "source": "s2",
                "kind": "k",
                "messages": 10,
                "markdown": "a/s2.md",
                "metadata": {"focus": "target"},
                "source_file": "/f2",
            },
        ]
        result = select_records(records, focus=["target"], max_sessions=10)
        # s2 should come first due to focus match
        assert len(result) >= 1

    def test_per_source_limit(self) -> None:
        records = [
            {
                "source": "s1",
                "kind": "k",
                "messages": i,
                "markdown": f"a/s1_{i}.md",
                "metadata": {},
                "source_file": f"/f{i}",
            }
            for i in range(10)
        ]
        result = select_records(records, focus=[], max_sessions=10)
        # Per-source limit is 4
        s1_count = sum(1 for r in result if r["source"] == "s1")
        assert s1_count <= 4


class TestEvidenceRecord:
    def test_creates_record(self, tmp_path: Path) -> None:
        config = ArchiveConfig(
            repo_root=tmp_path,
            archive_dir=tmp_path / "archive",
            raw_dir=tmp_path / "raw",
            sources=(),
        )
        # Create the markdown file
        md_dir = tmp_path / "archive" / "test-src"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / "session.md"
        md_path.write_text("# Test\n\nContent.\n", encoding="utf-8")

        record = {
            "source": "test-src",
            "kind": "claude",
            "messages": 5,
            "markdown": "archive/test-src/session.md",
            "metadata": {"session_id": "s1"},
        }
        result = evidence_record(config, record, max_chars=100)
        assert result["source"] == "test-src"
        assert result["kind"] == "claude"
        assert result["messages"] == 5
        assert "Test" in result["excerpt"]

    def test_missing_markdown_file(self, tmp_path: Path) -> None:
        config = ArchiveConfig(
            repo_root=tmp_path,
            archive_dir=tmp_path / "archive",
            raw_dir=tmp_path / "raw",
            sources=(),
        )
        record = {
            "source": "test-src",
            "kind": "claude",
            "messages": 3,
            "markdown": "archive/test-src/missing.md",
            "metadata": {},
        }
        result = evidence_record(config, record, max_chars=100)
        assert result["excerpt"] == ""


class TestBundleConstraints:
    def test_session_only(self) -> None:
        constraints = bundle_constraints("session-only")
        assert len(constraints) >= 5
        assert any("session" in c.lower() for c in constraints)

    def test_repo_read_only(self) -> None:
        constraints = bundle_constraints("repo-read-only")
        assert any("read-only" in c.lower() for c in constraints)

    def test_write_candidates(self) -> None:
        constraints = bundle_constraints("write-candidates")
        assert any("candidate" in c.lower() for c in constraints)


class TestProposalSchema:
    def test_returns_dict(self) -> None:
        schema = proposal_schema()
        assert isinstance(schema, dict)
        assert "id" in schema
        assert "title" in schema
        assert "scope" in schema
        assert "category" in schema
        assert "risk" in schema
        assert "confidence" in schema
        assert "source_kind" in schema
        assert "replay_of" in schema
        assert "trace" in schema


class TestRenderAgentPrompt:
    def test_renders(self) -> None:
        bundle = {
            "bundle_id": "test-bundle",
            "access_level": "session-only",
            "constraints": ["Do not promote.", "Use evidence."],
            "proposal_schema": {"id": "string"},
            "schema_contract": {"path": "baseline/SCHEMA.md", "content": "# Schema"},
        }
        prompt = render_agent_prompt(bundle)
        assert "AI Baseline Proposal Task" in prompt
        assert "test-bundle" in prompt
        assert "session-only" in prompt
        assert "baseline/SCHEMA.md" in prompt

    def test_schema_contract_loads_when_present(self, repo_root: Path) -> None:
        schema_path = repo_root / "baseline" / "SCHEMA.md"
        schema_path.write_text("# Local Schema\n\nUse markers.", encoding="utf-8")
        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=repo_root / "archive",
            raw_dir=repo_root / "raw",
            sources=(),
        )
        contract = baseline_schema_contract(config)
        assert contract == {
            "path": "baseline/SCHEMA.md",
            "content": "# Local Schema\n\nUse markers.",
        }

    def test_schema_contract_none_when_absent(self, tmp_path: Path) -> None:
        config = ArchiveConfig(
            repo_root=tmp_path,
            archive_dir=tmp_path / "archive",
            raw_dir=tmp_path / "raw",
            sources=(),
        )
        assert baseline_schema_contract(config) is None

    def test_prompt_omits_schema_section_when_absent(self) -> None:
        bundle = {
            "bundle_id": "test-bundle",
            "access_level": "session-only",
            "constraints": ["Do not promote."],
            "proposal_schema": {"id": "string"},
        }
        prompt = render_agent_prompt(bundle)
        assert "Baseline Schema Contract" not in prompt


class TestBulletList:
    def test_renders(self) -> None:
        result = bullet_list(["a", "b", "c"])
        assert result == "- a\n- b\n- c"

    def test_empty_list(self) -> None:
        result = bullet_list([])
        assert result == ""


class TestBaselineBundle:
    def test_dry_run(self, repo_root: Path) -> None:
        # Set up archive index
        archive_dir = repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        index_path = archive_dir / "index.jsonl"
        index_path.write_text(
            json.dumps(
                {
                    "source": "s",
                    "kind": "k",
                    "source_file": "/f",
                    "sha256": "a",
                    "messages": 1,
                    "markdown": "a/s.md",
                    "metadata": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=archive_dir,
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_bundle(config, max_sessions=1, dry_run=True)
        assert result == 0

    def test_writes_bundle(self, repo_root: Path) -> None:
        # Set up archive index with enough data
        archive_dir = repo_root / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Create markdown files referenced in the index
        md_dir = archive_dir / "test-src"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / "session.md"
        md_path.write_text("# Test\n\nContent.", encoding="utf-8")
        schema_path = repo_root / "baseline" / "SCHEMA.md"
        schema_path.write_text("# Local Schema\n\nUse markers.", encoding="utf-8")

        index_path = archive_dir / "index.jsonl"
        index_path.write_text(
            json.dumps(
                {
                    "source": "test-src",
                    "kind": "claude",
                    "source_file": "/f",
                    "sha256": "a",
                    "messages": 1,
                    "markdown": "archive/test-src/session.md",
                    "metadata": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        config = ArchiveConfig(
            repo_root=repo_root,
            archive_dir=archive_dir,
            raw_dir=repo_root / "raw",
            sources=(),
        )
        result = baseline_bundle(config, max_sessions=1)
        assert result == 0

        # Check bundle output
        evidence_dir = repo_root / "baseline" / "evidence"
        bundles = list(evidence_dir.glob("*.json"))
        prompts = list(evidence_dir.glob("*.prompt.md"))
        assert len(bundles) >= 1
        assert len(prompts) >= 1
        bundle_data = json.loads(bundles[0].read_text(encoding="utf-8"))
        prompt = prompts[0].read_text(encoding="utf-8")
        assert bundle_data["schema_contract"]["path"] == "baseline/SCHEMA.md"
        assert "Local Schema" in bundle_data["schema_contract"]["content"]
        assert "baseline/SCHEMA.md" in prompt
