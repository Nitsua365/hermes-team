from pathlib import Path
from pydantic import BaseModel, Field, computed_field
import yaml


class Config(BaseModel):
    image: str = "nousresearch/hermes-agent:latest"
    orchestrator_name: str = "hermes-orchestrator"
    orchestrator_port: int = 8642
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".hermes-team")
    project_dir: Path = Field(default_factory=Path.cwd)

    model_config = {"arbitrary_types_allowed": True}

    @computed_field
    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @computed_field
    @property
    def registry_path(self) -> Path:
        return self.project_dir / "registry.json"

    @computed_field
    @property
    def compose_file(self) -> Path:
        return self.project_dir / "docker-compose.yml"


def load_config(project_dir: Path | None = None) -> Config:
    project_dir = project_dir or Path.cwd()
    config_file = project_dir / "hermes-team.yaml"
    if config_file.exists():
        data = yaml.safe_load(config_file.read_text()) or {}
        if "data_dir" in data:
            data["data_dir"] = Path(data["data_dir"]).expanduser()
        return Config(project_dir=project_dir, **data)
    return Config(project_dir=project_dir)
