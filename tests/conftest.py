import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.agent import Agent
from orchestrator.config import Config
from orchestrator.manager import AgentManager


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config(project_dir: Path) -> Config:
    return Config(
        project_dir=project_dir,
        image="test-image:latest",
        orchestrator_profile=project_dir / ".hermes-test",
        agent_base_port=9000,
    )


@pytest.fixture
def mock_docker() -> MagicMock:
    docker = MagicMock()
    docker.run_agent.return_value = None
    docker.stop.return_value = None
    docker.remove.return_value = None
    docker.exec.return_value = MagicMock(returncode=0, stdout="", stderr="")
    docker.is_running.return_value = True
    docker.compose_build.return_value = None
    docker.compose_up.return_value = None
    return docker


@pytest.fixture
def manager(config: Config, mock_docker: MagicMock) -> AgentManager:
    m = AgentManager(config)
    m.docker = mock_docker
    return m


@pytest.fixture
def sample_agent(project_dir: Path) -> Agent:
    return Agent(
        name="sample-agent",
        summary="A sample agent for testing",
        port=9000,
        profile_dir=str(project_dir / "agents" / "sample-agent"),
        created_at=datetime.now(timezone.utc),
    )
