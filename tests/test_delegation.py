"""
Tests for orchestrator → sub-agent delegation.

Covers:
  - Agent.gateway_url construction
  - AgentManager.routing_candidates() — the lookup the orchestrator uses to
    decide which agent to route a task to
  - AgentManager.delegate_task() — HTTP POST to a sub-agent's Hermes gateway
  - create_agent tool handler — programmatic agent creation from inside the
    orchestrator container
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from orchestrator.agent import Agent
from orchestrator.manager import AgentManager, DelegationError


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def agent_alpha(project_dir: Path) -> Agent:
    return Agent(
        name="trend-analyst",
        summary="Researches market trends and competitive intelligence",
        port=9000,
        profile_dir=str(project_dir / "agents" / "trend-analyst"),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def agent_beta(project_dir: Path) -> Agent:
    return Agent(
        name="content-writer",
        summary="Writes blog posts, copy, and social media content",
        port=9001,
        profile_dir=str(project_dir / "agents" / "content-writer"),
        created_at=datetime.now(timezone.utc),
    )


def _chat_response(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}]
    }


# ── gateway URL ───────────────────────────────────────────────────────────────

class TestAgentGatewayUrl:
    def test_url_uses_localhost_and_port(self, agent_alpha: Agent):
        assert agent_alpha.gateway_url == "http://localhost:9000"

    def test_url_reflects_assigned_port(self):
        agent = Agent(
            name="custom",
            summary="custom",
            port=8765,
            profile_dir="/tmp/custom",
            created_at=datetime.now(timezone.utc),
        )
        assert agent.gateway_url == "http://localhost:8765"

    def test_unique_ports_produce_unique_urls(self, agent_alpha: Agent, agent_beta: Agent):
        assert agent_alpha.gateway_url != agent_beta.gateway_url


# ── routing candidates ────────────────────────────────────────────────────────

class TestRoutingCandidates:
    """
    The orchestrator queries routing_candidates() to decide which sub-agent
    to delegate a task to. Each candidate must expose name, summary, and
    gateway_url so the orchestrator has everything it needs to make the call.
    """

    def test_empty_when_no_agents_registered(self, manager: AgentManager):
        assert manager.routing_candidates() == []

    def test_returns_one_entry_per_active_agent(
        self, manager: AgentManager, agent_alpha: Agent, agent_beta: Agent
    ):
        manager.registry.add(agent_alpha)
        manager.registry.add(agent_beta)
        candidates = manager.routing_candidates()
        assert len(candidates) == 2

    def test_candidate_contains_name(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        candidate = manager.routing_candidates()[0]
        assert candidate["name"] == "trend-analyst"

    def test_candidate_contains_summary(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        candidate = manager.routing_candidates()[0]
        assert "market trends" in candidate["summary"]

    def test_candidate_contains_gateway_url(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        candidate = manager.routing_candidates()[0]
        assert candidate["gateway_url"] == "http://localhost:9000"

    def test_archived_agents_excluded(
        self, manager: AgentManager, agent_alpha: Agent, agent_beta: Agent
    ):
        manager.registry.add(agent_alpha)
        manager.registry.add(agent_beta)
        manager.registry.archive("trend-analyst")
        candidates = manager.routing_candidates()
        names = [c["name"] for c in candidates]
        assert "trend-analyst" not in names
        assert "content-writer" in names


# ── delegate_task ─────────────────────────────────────────────────────────────

class TestDelegateTask:
    """delegate_task POSTs to the sub-agent's Hermes gateway and returns the
    parsed JSON response."""

    def test_posts_to_agent_gateway_url(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = _chat_response("Here is my analysis.")

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
            manager.delegate_task("trend-analyst", "Analyse Q2 trends")

        call_args = mock_client_cls.return_value.__enter__.return_value.post.call_args
        assert call_args[0][0] == "http://localhost:9000/v1/chat/completions"

    def test_payload_contains_user_message(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = _chat_response("Done.")

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
            manager.delegate_task("trend-analyst", "Analyse Q2 trends")

        payload = mock_client_cls.return_value.__enter__.return_value.post.call_args[1]["json"]
        messages = payload["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Analyse Q2 trends"

    def test_returns_parsed_response(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        expected = _chat_response("Trends are up 12% this quarter.")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = expected

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
            result = manager.delegate_task("trend-analyst", "Q2 summary?")

        assert result == expected
        assert "choices" in result

    def test_raises_delegation_error_on_http_error(
        self, manager: AgentManager, agent_alpha: Agent
    ):
        manager.registry.add(agent_alpha)
        http_err = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(status_code=500)
        )

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.side_effect = http_err
            with pytest.raises(DelegationError, match="500"):
                manager.delegate_task("trend-analyst", "Do something")

    def test_raises_delegation_error_on_connection_failure(
        self, manager: AgentManager, agent_alpha: Agent
    ):
        manager.registry.add(agent_alpha)

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.side_effect = (
                httpx.ConnectError("Connection refused")
            )
            with pytest.raises(DelegationError, match="Could not reach agent"):
                manager.delegate_task("trend-analyst", "Hello")

    def test_raises_value_error_for_unknown_agent(self, manager: AgentManager):
        with pytest.raises(ValueError, match="not found"):
            manager.delegate_task("nonexistent", "Hello")

    def test_uses_120s_timeout(self, manager: AgentManager, agent_alpha: Agent):
        manager.registry.add(agent_alpha)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = _chat_response("ok")

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
            manager.delegate_task("trend-analyst", "ping")

        mock_client_cls.assert_called_once_with(timeout=120)


# ── create_agent tool handler ─────────────────────────────────────────────────

class TestCreateAgentTool:
    """
    The create_agent tool is embedded in the orchestrator container so the
    orchestrator Hermes agent can spin up sub-agents programmatically.
    Verify the handler calls the manager correctly and surfaces the right info.
    """

    def _invoke(self, name: str, summary: str, manager: AgentManager) -> dict:
        from tools.create_agent import handle_create_agent
        with patch("tools.create_agent._USE_PACKAGE", True), \
             patch("tools.create_agent.load_config") as mock_cfg, \
             patch("tools.create_agent.AgentManager") as mock_mgr_cls:
            mock_mgr_cls.return_value = manager
            mock_cfg.return_value = MagicMock()
            result_str = handle_create_agent(name=name, summary=summary)
        return json.loads(result_str)

    def test_returns_created_status(self, manager: AgentManager):
        result = self._invoke("trend-analyst", "Researches trends", manager)
        assert result["status"] == "created"

    def test_returns_agent_name(self, manager: AgentManager):
        result = self._invoke("trend-analyst", "Researches trends", manager)
        assert result["name"] == "trend-analyst"

    def test_returns_gateway_url(self, manager: AgentManager):
        result = self._invoke("trend-analyst", "Researches trends", manager)
        assert result["gateway"].startswith("http://localhost:")

    def test_returns_next_step_hint(self, manager: AgentManager):
        result = self._invoke("trend-analyst", "Researches trends", manager)
        assert "next_step" in result
        assert "trend-analyst" in result["next_step"]

    def test_returns_error_on_duplicate_name(self, manager: AgentManager):
        manager.add_agent("trend-analyst", "First")
        result = self._invoke("trend-analyst", "Duplicate", manager)
        assert "error" in result

    def test_returns_error_on_invalid_name(self, manager: AgentManager):
        result = self._invoke("Bad Name!", "Invalid", manager)
        assert "error" in result


# ── end-to-end delegation sequence ───────────────────────────────────────────

class TestDelegationSequence:
    """
    Simulate the full orchestrator → sub-agent flow:
      1. Orchestrator queries routing_candidates() to select an agent
      2. Orchestrator calls delegate_task() with the chosen agent
      3. Response is correctly returned
    """

    def test_orchestrator_selects_and_delegates(
        self, manager: AgentManager, agent_alpha: Agent, agent_beta: Agent
    ):
        manager.registry.add(agent_alpha)
        manager.registry.add(agent_beta)

        # Step 1 — routing decision: pick the agent whose summary matches
        task = "Research competitor pricing"
        candidates = manager.routing_candidates()
        chosen = next(c for c in candidates if "trends" in c["summary"].lower())
        assert chosen["name"] == "trend-analyst"

        # Step 2 — delegate to chosen agent
        expected_reply = _chat_response("Competitor pricing analysis complete.")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = expected_reply

        with patch("orchestrator.manager.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
            result = manager.delegate_task(chosen["name"], task)

        # Step 3 — verify response
        assert result["choices"][0]["message"]["content"] == "Competitor pricing analysis complete."
