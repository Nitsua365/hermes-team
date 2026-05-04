"""
Tests for the Kanban-based orchestrator → sub-agent delegation architecture.

Covers:
  - Profile creation installs the kanban-worker skill (dispatcher prerequisite)
  - MEMORY.md contains role definition + summary (agent context)
  - list_profiles tool reads registry and returns correct routing candidates
  - create_agent tool creates a profile and returns Kanban-ready response
  - DAG routing: orchestrator selects the right profile from list_profiles output
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.agent import Agent
from orchestrator.manager import AgentManager


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def agent_researcher(manager: AgentManager) -> Agent:
    return manager.add_agent(
        "researcher",
        "Researches market trends and competitive intelligence",
    )


@pytest.fixture
def agent_writer(manager: AgentManager) -> Agent:
    return manager.add_agent(
        "writer",
        "Writes blog posts, reports, and long-form content",
    )


# ── profile structure ─────────────────────────────────────────────────────────

class TestProfileStructure:
    """
    When agent add is called, the profile must be structured so the Hermes
    dispatcher can spawn it: a profile directory, MEMORY.md with role context,
    and the kanban-worker skill installed.
    """

    def test_profile_directory_created(self, agent_researcher: Agent, data_dir: Path):
        assert (data_dir / "profiles" / "researcher").is_dir()

    def test_memories_directory_created(self, agent_researcher: Agent, data_dir: Path):
        assert (data_dir / "profiles" / "researcher" / "memories").is_dir()

    def test_memory_contains_summary(self, agent_researcher: Agent, data_dir: Path):
        memory = (
            data_dir / "profiles" / "researcher" / "memories" / "MEMORY.md"
        ).read_text()
        assert "market trends" in memory

    def test_memory_contains_role_section(self, agent_researcher: Agent, data_dir: Path):
        memory = (
            data_dir / "profiles" / "researcher" / "memories" / "MEMORY.md"
        ).read_text()
        assert "## Role" in memory

    def test_kanban_worker_skill_installed(self, agent_researcher: Agent, data_dir: Path):
        skill = (
            data_dir
            / "profiles"
            / "researcher"
            / "skills"
            / "kanban-worker"
            / "SKILL.md"
        )
        assert skill.exists()

    def test_kanban_worker_skill_has_content(self, agent_researcher: Agent, data_dir: Path):
        skill = (
            data_dir
            / "profiles"
            / "researcher"
            / "skills"
            / "kanban-worker"
            / "SKILL.md"
        ).read_text()
        assert "kanban_show" in skill
        assert "kanban_complete" in skill

    def test_second_profile_gets_independent_skill_copy(
        self, agent_researcher: Agent, agent_writer: Agent, data_dir: Path
    ):
        r_skill = data_dir / "profiles" / "researcher" / "skills" / "kanban-worker"
        w_skill = data_dir / "profiles" / "writer" / "skills" / "kanban-worker"
        assert r_skill.exists()
        assert w_skill.exists()
        assert r_skill != w_skill


# ── list_profiles tool ────────────────────────────────────────────────────────

class TestListProfilesTool:
    """
    The orchestrator calls list_profiles() to get routing candidates before
    building a Kanban DAG. It must return name + summary for every active profile.
    """

    def _call(self, project_dir: Path) -> dict:
        from tools.list_profiles import handle_list_profiles
        with patch.dict("os.environ", {"PROJECT_DIR": str(project_dir)}):
            return json.loads(handle_list_profiles())

    def test_returns_empty_when_no_registry(self, tmp_path: Path):
        result = self._call(tmp_path)
        assert result["profiles"] == []

    def test_returns_registered_profiles(
        self, manager: AgentManager, agent_researcher: Agent, project_dir: Path
    ):
        result = self._call(project_dir)
        names = [p["name"] for p in result["profiles"]]
        assert "researcher" in names

    def test_profile_entry_contains_summary(
        self, manager: AgentManager, agent_researcher: Agent, project_dir: Path
    ):
        result = self._call(project_dir)
        profile = next(p for p in result["profiles"] if p["name"] == "researcher")
        assert "market trends" in profile["summary"]

    def test_archived_profiles_excluded(
        self,
        manager: AgentManager,
        agent_researcher: Agent,
        agent_writer: Agent,
        project_dir: Path,
    ):
        manager.remove_agent("researcher")
        result = self._call(project_dir)
        names = [p["name"] for p in result["profiles"]]
        assert "researcher" not in names
        assert "writer" in names

    def test_multiple_profiles_all_returned(
        self,
        manager: AgentManager,
        agent_researcher: Agent,
        agent_writer: Agent,
        project_dir: Path,
    ):
        result = self._call(project_dir)
        assert len(result["profiles"]) == 2


# ── create_agent tool ─────────────────────────────────────────────────────────

class TestCreateAgentTool:
    """
    The orchestrator agent can create new profiles on-the-fly using the
    create_agent tool. The response must confirm the profile is Kanban-ready.
    """

    def _invoke(self, name: str, summary: str, manager: AgentManager) -> dict:
        from tools.create_agent import handle_create_agent
        with patch("tools.create_agent._USE_PACKAGE", True), \
             patch("tools.create_agent.load_config") as mock_cfg, \
             patch("tools.create_agent.AgentManager") as mock_mgr_cls:
            mock_mgr_cls.return_value = manager
            mock_cfg.return_value = MagicMock()
            return json.loads(handle_create_agent(name=name, summary=summary))

    def test_returns_created_status(self, manager: AgentManager):
        result = self._invoke("analyst", "Analyses data", manager)
        assert result["status"] == "created"

    def test_returns_agent_name(self, manager: AgentManager):
        result = self._invoke("analyst", "Analyses data", manager)
        assert result["name"] == "analyst"

    def test_returns_profile_dir(self, manager: AgentManager):
        result = self._invoke("analyst", "Analyses data", manager)
        assert "profile_dir" in result
        assert "analyst" in result["profile_dir"]

    def test_response_mentions_kanban(self, manager: AgentManager):
        result = self._invoke("analyst", "Analyses data", manager)
        assert "Kanban" in result["next_step"] or "kanban" in result["next_step"].lower()

    def test_error_on_duplicate_name(self, manager: AgentManager):
        manager.add_agent("analyst", "First")
        result = self._invoke("analyst", "Duplicate", manager)
        assert "error" in result

    def test_error_on_invalid_name(self, manager: AgentManager):
        result = self._invoke("Bad Name!", "Invalid", manager)
        assert "error" in result


# ── DAG routing sequence ──────────────────────────────────────────────────────

class TestDAGRoutingSequence:
    """
    Simulate the orchestrator's routing decision:
      1. Orchestrator calls list_profiles() to see available agents
      2. Orchestrator matches each task to a profile by summary
      3. Each matched profile has the kanban-worker skill ready for dispatch
    """

    def test_orchestrator_selects_correct_profile_for_research_task(
        self,
        manager: AgentManager,
        agent_researcher: Agent,
        agent_writer: Agent,
        project_dir: Path,
    ):
        from tools.list_profiles import handle_list_profiles

        with patch.dict("os.environ", {"PROJECT_DIR": str(project_dir)}):
            candidates = json.loads(handle_list_profiles())["profiles"]

        task = "Research Q2 AI chip market trends"
        chosen = next(
            c for c in candidates if "trend" in c["summary"].lower() or "research" in c["summary"].lower()
        )
        assert chosen["name"] == "researcher"

    def test_all_chosen_profiles_have_kanban_worker_installed(
        self,
        manager: AgentManager,
        agent_researcher: Agent,
        agent_writer: Agent,
        data_dir: Path,
        project_dir: Path,
    ):
        from tools.list_profiles import handle_list_profiles

        with patch.dict("os.environ", {"PROJECT_DIR": str(project_dir)}):
            candidates = json.loads(handle_list_profiles())["profiles"]

        for candidate in candidates:
            skill_path = (
                data_dir
                / "profiles"
                / candidate["name"]
                / "skills"
                / "kanban-worker"
                / "SKILL.md"
            )
            assert skill_path.exists(), (
                f"Profile '{candidate['name']}' is missing kanban-worker skill — "
                "dispatcher cannot spawn it"
            )
