import json
from pathlib import Path
from typing import Optional

from .agent import Agent


class AgentRegistry:
    def __init__(self, path: Path):
        self.path = path
        self._active: dict[str, Agent] = {}
        self._archived: dict[str, Agent] = {}
        if path.exists():
            self._load()

    def _load(self) -> None:
        data = json.loads(self.path.read_text())
        self._active = {k: Agent(**v) for k, v in data.get("active", {}).items()}
        self._archived = {k: Agent(**v) for k, v in data.get("archived", {}).items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "active": {k: v.model_dump(mode="json") for k, v in self._active.items()},
            "archived": {k: v.model_dump(mode="json") for k, v in self._archived.items()},
        }
        self.path.write_text(json.dumps(data, indent=2, default=str))

    def add(self, agent: Agent) -> None:
        self._active[agent.name] = agent
        self.save()

    def update(self, agent: Agent) -> None:
        self._active[agent.name] = agent
        self.save()

    def get(self, name: str) -> Optional[Agent]:
        return self._active.get(name)

    def get_archived(self, name: str) -> Optional[Agent]:
        return self._archived.get(name)

    def archive(self, name: str) -> None:
        agent = self._active.pop(name)
        agent.status = "archived"
        self._archived[name] = agent
        self.save()

    def restore(self, name: str, new_profile_dir: str) -> Agent:
        agent = self._archived.pop(name)
        agent.profile_dir = new_profile_dir
        agent.status = "active"
        self._active[name] = agent
        self.save()
        return agent

    def all_active(self) -> list[Agent]:
        return list(self._active.values())

    def all_archived(self) -> list[Agent]:
        return list(self._archived.values())
