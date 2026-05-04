import pytest
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.agent import Agent
from orchestrator.config import Config
from orchestrator.manager import AgentManager

from datetime import datetime, timezone


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def config(project_dir: Path, data_dir: Path) -> Config:
    return Config(
        project_dir=project_dir,
        data_dir=data_dir,
        image="test-image:latest",
    )


@pytest.fixture
def mock_docker() -> MagicMock:
    docker = MagicMock()
    docker.compose_build.return_value = None
    docker.compose_up.return_value = None
    docker.setup_interactive.return_value = None
    return docker


@pytest.fixture
def manager(config: Config, mock_docker: MagicMock) -> AgentManager:
    m = AgentManager(config)
    m.docker = mock_docker
    return m


@pytest.fixture
def sample_agent(data_dir: Path) -> Agent:
    return Agent(
        name="sample-agent",
        summary="A sample agent for testing",
        profile_dir=str(data_dir / "profiles" / "sample-agent"),
        created_at=datetime.now(timezone.utc),
    )
