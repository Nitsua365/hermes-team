import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from orchestrator.agent import Agent
from orchestrator.cli import cli

_INIT_GUARD = "orchestrator.cli.already_initialized"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def agent() -> Agent:
    return Agent(
        name="test-agent",
        summary="A test agent",
        profile_dir="/tmp/profiles/test-agent",
        created_at=datetime.now(timezone.utc),
    )


def _mock_manager(agent: Agent | None = None) -> MagicMock:
    m = MagicMock()
    m.config.orchestrator_port = 8642
    m.config.image = "test-image:latest"
    m.registry.all_active.return_value = [agent] if agent else []
    if agent:
        m.get_agent.return_value = agent
    return m


# ── start ──────────────────────────────────────────────────────────────────────

class TestStart:
    def test_calls_start_orchestrator(self, runner: CliRunner):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            mock_get.return_value = _mock_manager()
            result = runner.invoke(cli, ["start"])
        assert result.exit_code == 0

    def test_shows_url_on_success(self, runner: CliRunner):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            mock_get.return_value = _mock_manager()
            result = runner.invoke(cli, ["start"])
        assert "8642" in result.output

    def test_exits_1_when_not_initialized(self, runner: CliRunner):
        with patch(_INIT_GUARD, return_value=False):
            result = runner.invoke(cli, ["start"])
        assert result.exit_code == 1
        assert "orchestrator init" in result.output


# ── agent add ──────────────────────────────────────────────────────────────────

class TestAgentAdd:
    def test_success(self, runner: CliRunner, agent: Agent):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager(agent)
            m.add_agent.return_value = agent
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "add", "test-agent", "--summary", "A test agent"]
            )
        assert result.exit_code == 0
        assert "test-agent" in result.output

    def test_prompts_for_summary_when_omitted(self, runner: CliRunner, agent: Agent):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager(agent)
            m.add_agent.return_value = agent
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "add", "test-agent"], input="A test agent\n"
            )
        assert result.exit_code == 0

    def test_exits_1_on_duplicate(self, runner: CliRunner):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            m.add_agent.side_effect = ValueError("already exists")
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "add", "test-agent", "--summary", "dup"]
            )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_exits_1_on_invalid_name(self, runner: CliRunner):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            m.add_agent.side_effect = ValueError("Invalid agent name")
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "add", "Bad Name", "--summary", "test"]
            )
        assert result.exit_code == 1

    def test_exits_1_when_not_initialized(self, runner: CliRunner):
        with patch(_INIT_GUARD, return_value=False):
            result = runner.invoke(
                cli, ["agent", "add", "test-agent", "--summary", "test"]
            )
        assert result.exit_code == 1
        assert "orchestrator init" in result.output

    def test_shows_profile_path(self, runner: CliRunner, agent: Agent):
        with patch(_INIT_GUARD, return_value=True), \
             patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager(agent)
            m.add_agent.return_value = agent
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "add", "test-agent", "--summary", "A test agent"]
            )
        assert "Profile" in result.output
        assert "kanban-worker" in result.output


# ── agent remove ───────────────────────────────────────────────────────────────

class TestAgentRemove:
    def test_success_with_confirmation(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "remove", "test-agent"], input="y\n")
        assert result.exit_code == 0
        m.remove_agent.assert_called_once_with("test-agent")

    def test_aborts_without_confirmation(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "remove", "test-agent"], input="n\n")
        assert result.exit_code != 0
        m.remove_agent.assert_not_called()

    def test_exits_1_if_not_found(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            m.remove_agent.side_effect = ValueError("not found")
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "remove", "nonexistent"], input="y\n")
        assert result.exit_code == 1


# ── agent recover ──────────────────────────────────────────────────────────────

class TestAgentRecover:
    def test_success(self, runner: CliRunner, agent: Agent):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager(agent)
            m.recover_agent.return_value = agent
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "recover", "test-agent"])
        assert result.exit_code == 0
        assert "test-agent" in result.output

    def test_exits_1_if_no_archive(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            m.recover_agent.side_effect = ValueError("No archive")
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "recover", "nonexistent"])
        assert result.exit_code == 1


# ── agent list ─────────────────────────────────────────────────────────────────

class TestAgentList:
    def test_shows_table_with_agents(self, runner: CliRunner, agent: Agent):
        with patch("orchestrator.cli._manager") as mock_get:
            mock_get.return_value = _mock_manager(agent)
            result = runner.invoke(cli, ["agent", "list"])
        assert result.exit_code == 0
        assert "test-agent" in result.output
        assert "A test agent" in result.output

    def test_shows_message_when_empty(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            mock_get.return_value = _mock_manager()
            result = runner.invoke(cli, ["agent", "list"])
        assert result.exit_code == 0
        assert "No agent profiles" in result.output


# ── goal commands ──────────────────────────────────────────────────────────────

class TestGoalSet:
    def test_success(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "goal", "set", "test-agent", "Research weekly trends"]
            )
        assert result.exit_code == 0
        m.set_goal.assert_called_once_with("test-agent", "Research weekly trends")

    def test_exits_1_if_agent_not_found(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            m.set_goal.side_effect = ValueError("not found")
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "goal", "set", "nonexistent", "A goal"]
            )
        assert result.exit_code == 1


class TestGoalList:
    def test_shows_goals(self, runner: CliRunner, agent: Agent):
        agent.goals = ["Goal one", "Goal two"]
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager(agent)
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "goal", "list", "test-agent"])
        assert result.exit_code == 0
        assert "Goal one" in result.output
        assert "Goal two" in result.output

    def test_shows_empty_message(self, runner: CliRunner, agent: Agent):
        agent.goals = []
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager(agent)
            mock_get.return_value = m
            result = runner.invoke(cli, ["agent", "goal", "list", "test-agent"])
        assert result.exit_code == 0
        assert "No goals" in result.output


class TestGoalClear:
    def test_success_with_confirmation(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "goal", "clear", "test-agent"], input="y\n"
            )
        assert result.exit_code == 0
        m.clear_goals.assert_called_once_with("test-agent")

    def test_aborts_without_confirmation(self, runner: CliRunner):
        with patch("orchestrator.cli._manager") as mock_get:
            m = _mock_manager()
            mock_get.return_value = m
            result = runner.invoke(
                cli, ["agent", "goal", "clear", "test-agent"], input="n\n"
            )
        m.clear_goals.assert_not_called()
