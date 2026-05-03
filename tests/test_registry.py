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
        port=8650,
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
        assert loaded.port == agent.port

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
        registry.restore("test-agent", 8651, "/tmp/agents/test-agent-new")
        assert registry.get("test-agent") is not None

    def test_restore_removes_from_archived(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        registry.restore("test-agent", 8651, "/tmp/agents/test-agent-new")
        assert registry.get_archived("test-agent") is None

    def test_restore_updates_port(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)
        registry.archive("test-agent")
        restored = registry.restore("test-agent", 8999, "/tmp/agents/test-agent")
        assert restored.port == 8999


class TestNextPort:
    def test_returns_base_when_empty(self, registry: AgentRegistry):
        assert registry.next_port(8650) == 8650

    def test_skips_used_port(self, registry: AgentRegistry, agent: Agent):
        registry.add(agent)  # port 8650
        assert registry.next_port(8650) == 8651

    def test_skips_multiple_used_ports(self, registry: AgentRegistry):
        for i, port in enumerate([8650, 8651, 8652]):
            registry.add(Agent(
                name=f"agent-{i}",
                summary="test",
                port=port,
                profile_dir=f"/tmp/{i}",
                created_at=datetime.now(timezone.utc),
            ))
        assert registry.next_port(8650) == 8653


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
