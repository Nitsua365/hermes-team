import pytest
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.agent import Agent
from orchestrator.registry import AgentRegistry


@pytest.fixture
def registry(tmp_path: Path) -> AgentRegistry:
    return AgentRegistry(tmp_path / "registry.json")


@pytest.fixture
def agent() -> Agent:
    return Agent(
        name="test-agent",
        summary="A test agent",
        profile_dir="/tmp/agents/test-agent",
        created_at=datetime.now(timezone.utc),
    )


class TestAddAndGet:
    def test_add_then_get(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        result = registry.get("test-agent")
        assert result is not None
        assert result.name == "test-agent"

    def test_get_returns_none_for_missing(self, registry: AgentRegistry):
        assert registry.get("nonexistent") is None

    def test_get_archived_returns_none_when_active(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        assert registry.get_archived("test-agent") is None


class TestPersistence:
    def test_survives_reload(self, tmp_path: Path, agent: Agent):
        r1 = AgentRegistry(tmp_path / "registry.json")
        r1.add(agent)

        r2 = AgentRegistry(tmp_path / "registry.json")
        loaded = r2.get("test-agent")
        assert loaded is not None
        assert loaded.name == agent.name
        assert loaded.summary == agent.summary

    def test_archived_survives_reload(self, tmp_path: Path, agent: Agent):
        r1 = AgentRegistry(tmp_path / "registry.json")
        r1.add(agent)
        r1.archive("test-agent")

        r2 = AgentRegistry(tmp_path / "registry.json")
        assert r2.get("test-agent") is None
        assert r2.get_archived("test-agent") is not None


class TestArchiveAndRestore:
    def test_archive_removes_from_active(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        assert registry.get("test-agent") is None

    def test_archive_appears_in_archived(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        assert registry.get_archived("test-agent") is not None

    def test_restore_appears_in_active(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        registry.restore("test-agent", "/tmp/agents/test-agent-new")
        assert registry.get("test-agent") is not None

    def test_restore_removes_from_archived(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        registry.restore("test-agent", "/tmp/agents/test-agent-new")
        assert registry.get_archived("test-agent") is None

    def test_restore_updates_profile_dir(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        restored = registry.restore("test-agent", "/tmp/agents/test-agent-new")
        assert restored.profile_dir == "/tmp/agents/test-agent-new"


class TestAllActive:
    def test_empty_by_default(self, registry: AgentRegistry):
        assert registry.all_active() == []

    def test_returns_added_agents(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        assert len(registry.all_active()) == 1

    def test_excludes_archived(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        assert registry.all_active() == []
