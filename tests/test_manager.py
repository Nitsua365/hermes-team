import pytest
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.manager import AgentManager, _add_goal, _remove_goals_section, _validate_name


# ── name validation ────────────────────────────────────────────────────────────

class TestValidateName:
    def test_accepts_simple(self):
        _validate_name("research")

    def test_accepts_hyphenated(self):
        _validate_name("trend-analyst")

    def test_accepts_alphanumeric(self):
        _validate_name("agent1")

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            _validate_name("TrendAnalyst")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            _validate_name("trend analyst")

    def test_rejects_leading_hyphen(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            _validate_name("-trend")

    def test_rejects_trailing_hyphen(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            _validate_name("trend-")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            _validate_name("trend@analyst")


# ── add_agent ──────────────────────────────────────────────────────────────────

class TestAddAgent:
    def test_creates_profile_directory(self, manager: AgentManager, project_dir: Path):
        manager.add_agent("test-agent", "A test agent")
        assert (project_dir / "agents" / "test-agent").is_dir()

    def test_registers_agent_in_registry(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        assert manager.registry.get("test-agent") is not None

    def test_stores_summary(self, manager: AgentManager):
        a = manager.add_agent("test-agent", "My summary")
        assert a.summary == "My summary"

    def test_assigns_base_port_when_registry_empty(self, manager: AgentManager):
        a = manager.add_agent("test-agent", "First")
        assert a.port == manager.config.agent_base_port

    def test_assigns_unique_ports_for_multiple_agents(self, manager: AgentManager):
        a1 = manager.add_agent("agent-one", "First")
        a2 = manager.add_agent("agent-two", "Second")
        assert a1.port != a2.port

    def test_calls_docker_run(self, manager: AgentManager, mock_docker: MagicMock):
        manager.add_agent("test-agent", "A test agent")
        mock_docker.run_agent.assert_called_once()

    def test_raises_if_name_already_exists(self, manager: AgentManager):
        manager.add_agent("test-agent", "First")
        with pytest.raises(ValueError, match="already exists"):
            manager.add_agent("test-agent", "Duplicate")

    def test_raises_on_invalid_name(self, manager: AgentManager):
        with pytest.raises(ValueError, match="Invalid agent name"):
            manager.add_agent("Bad Name!", "Test")


# ── remove_agent ───────────────────────────────────────────────────────────────

class TestRemoveAgent:
    def test_archives_profile_directory(self, manager: AgentManager, project_dir: Path):
        manager.add_agent("test-agent", "A test agent")
        manager.remove_agent("test-agent")
        assert (project_dir / "agents" / ".archive" / "test-agent").is_dir()
        assert not (project_dir / "agents" / "test-agent").exists()

    def test_removes_from_active_registry(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.remove_agent("test-agent")
        assert manager.registry.get("test-agent") is None

    def test_stops_and_removes_container(self, manager: AgentManager, mock_docker: MagicMock):
        manager.add_agent("test-agent", "A test agent")
        manager.remove_agent("test-agent")
        mock_docker.stop.assert_called_with("test-agent")
        mock_docker.remove.assert_called_with("test-agent")

    def test_raises_if_agent_not_found(self, manager: AgentManager):
        with pytest.raises(ValueError, match="not found"):
            manager.remove_agent("nonexistent")


# ── recover_agent ──────────────────────────────────────────────────────────────

class TestRecoverAgent:
    def test_restores_profile_directory(self, manager: AgentManager, project_dir: Path):
        manager.add_agent("test-agent", "A test agent")
        manager.remove_agent("test-agent")
        manager.recover_agent("test-agent")
        assert (project_dir / "agents" / "test-agent").is_dir()

    def test_re_registers_in_active_registry(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.remove_agent("test-agent")
        manager.recover_agent("test-agent")
        assert manager.registry.get("test-agent") is not None

    def test_assigns_a_valid_port_on_recovery(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.remove_agent("test-agent")
        recovered = manager.recover_agent("test-agent")
        assert isinstance(recovered.port, int)
        assert recovered.port >= manager.config.agent_base_port

    def test_raises_if_no_archive_exists(self, manager: AgentManager):
        with pytest.raises(ValueError, match="No archive"):
            manager.recover_agent("nonexistent")


# ── set_goal ───────────────────────────────────────────────────────────────────

class TestSetGoal:
    def test_writes_goal_to_memory_file(self, manager: AgentManager, project_dir: Path):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "Research market trends weekly")

        memory_file = project_dir / "agents" / "test-agent" / "memories" / "MEMORY.md"
        assert memory_file.exists()
        assert "Research market trends weekly" in memory_file.read_text()

    def test_creates_memories_directory(self, manager: AgentManager, project_dir: Path):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "A goal")
        assert (project_dir / "agents" / "test-agent" / "memories").is_dir()

    def test_stores_goal_in_registry(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "Research market trends weekly")
        assert "Research market trends weekly" in manager.registry.get("test-agent").goals

    def test_multiple_goals_accumulate_in_registry(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "Goal one")
        manager.set_goal("test-agent", "Goal two")
        assert len(manager.registry.get("test-agent").goals) == 2

    def test_multiple_goals_appear_in_memory_file(self, manager: AgentManager, project_dir: Path):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "Goal one")
        manager.set_goal("test-agent", "Goal two")
        text = (project_dir / "agents" / "test-agent" / "memories" / "MEMORY.md").read_text()
        assert "Goal one" in text
        assert "Goal two" in text

    def test_raises_if_agent_not_found(self, manager: AgentManager):
        with pytest.raises(ValueError, match="not found"):
            manager.set_goal("nonexistent", "A goal")


# ── clear_goals ────────────────────────────────────────────────────────────────

class TestClearGoals:
    def test_removes_goals_from_registry(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "A goal")
        manager.clear_goals("test-agent")
        assert manager.registry.get("test-agent").goals == []

    def test_removes_goals_section_from_memory_file(
        self, manager: AgentManager, project_dir: Path
    ):
        manager.add_agent("test-agent", "A test agent")
        manager.set_goal("test-agent", "Goal to remove")
        manager.clear_goals("test-agent")
        memory_file = project_dir / "agents" / "test-agent" / "memories" / "MEMORY.md"
        if memory_file.exists():
            assert "Goal to remove" not in memory_file.read_text()

    def test_safe_when_no_goals_exist(self, manager: AgentManager):
        manager.add_agent("test-agent", "A test agent")
        manager.clear_goals("test-agent")  # must not raise


# ── goal helper functions ──────────────────────────────────────────────────────

class TestAddGoalHelper:
    def test_creates_header_and_entry_on_empty_content(self):
        result = _add_goal("", "Monitor competitor pricing")
        assert "## Orchestrator Goals" in result
        assert "- Monitor competitor pricing" in result

    def test_appends_to_existing_goals_section(self):
        content = "## Orchestrator Goals\n- First goal\n"
        result = _add_goal(content, "Second goal")
        assert "First goal" in result
        assert "Second goal" in result

    def test_preserves_existing_memory_content(self):
        content = "## Environment\n- macOS 14\n"
        result = _add_goal(content, "New goal")
        assert "## Environment" in result
        assert "macOS 14" in result

    def test_does_not_duplicate_header(self):
        content = "## Orchestrator Goals\n- Existing\n"
        result = _add_goal(content, "New goal")
        assert result.count("## Orchestrator Goals") == 1


class TestRemoveGoalsSectionHelper:
    def test_removes_goals_section(self):
        content = "## Other\n- item\n\n## Orchestrator Goals\n- goal1\n- goal2\n"
        result = _remove_goals_section(content)
        assert "## Orchestrator Goals" not in result
        assert "goal1" not in result

    def test_preserves_other_sections(self):
        content = "## Environment\n- macOS\n\n## Orchestrator Goals\n- a goal\n"
        result = _remove_goals_section(content)
        assert "## Environment" in result
        assert "macOS" in result

    def test_safe_on_content_with_no_goals(self):
        content = "## Environment\n- macOS\n"
        result = _remove_goals_section(content)
        assert "## Environment" in result
