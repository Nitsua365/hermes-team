import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .agent import Agent
from .config import Config
from .docker import DockerClient
from .registry import AgentRegistry


class DelegationError(Exception):
    pass

_GOALS_HEADER = "## Orchestrator Goals"
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$")


class AgentManager:
    def __init__(self, config: Config):
        self.config = config
        self.docker = DockerClient()
        self.registry = AgentRegistry(config.registry_path)

    # ── orchestrator ─────────────────────────────────────────────────────────

    def start_orchestrator(self) -> None:
        self.docker.compose_build(str(self.config.compose_file))
        self.docker.compose_up(str(self.config.compose_file))

        profile = self.config.orchestrator_profile
        profile.mkdir(parents=True, exist_ok=True)

        sentinel = profile / ".initialized"
        if not sentinel.exists():
            self.docker.setup_interactive(str(profile), self.config.image)
            sentinel.touch()

    # ── agents ────────────────────────────────────────────────────────────────

    def add_agent(self, name: str, summary: str) -> Agent:
        _validate_name(name)

        if self.registry.get(name):
            raise ValueError(f"Agent '{name}' already exists.")

        profile_dir = self.config.agents_dir / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        port = self.registry.next_port(self.config.agent_base_port)
        self.docker.run_agent(name, port, str(profile_dir), self.config.image)

        agent = Agent(
            name=name,
            summary=summary,
            port=port,
            profile_dir=str(profile_dir),
            created_at=datetime.now(timezone.utc),
        )
        self.registry.add(agent)
        return agent

    def remove_agent(self, name: str) -> None:
        agent = self.get_agent(name)

        self.docker.stop(name)
        self.docker.remove(name)

        archive = self.config.agents_dir / ".archive" / name
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(agent.profile_dir)), str(archive))

        self.registry.archive(name)

    def recover_agent(self, name: str) -> Agent:
        archived = self.registry.get_archived(name)
        if not archived:
            raise ValueError(f"No archive found for '{name}'.")

        archive = self.config.agents_dir / ".archive" / name
        if not archive.exists():
            raise ValueError(f"Archive directory missing: {archive}")

        profile_dir = self.config.agents_dir / name
        shutil.move(str(archive), str(profile_dir))

        port = self.registry.next_port(self.config.agent_base_port)
        self.docker.run_agent(name, port, str(profile_dir), self.config.image)

        return self.registry.restore(name, port, str(profile_dir))

    # ── goals ─────────────────────────────────────────────────────────────────

    def set_goal(self, agent_name: str, goal: str) -> None:
        """
        Persist a goal for a sub-agent by writing it to their MEMORY.md.

        Hermes injects MEMORY.md into every session's system prompt, so the
        goal is active from the agent's next conversation onward without
        requiring a container restart.

        This mirrors hermes' own /goal mechanism: goals survive across sessions
        and the agent is aware of them at the start of each turn.
        """
        agent = self.get_agent(agent_name)

        memory_dir = Path(agent.profile_dir) / "memories"
        memory_dir.mkdir(exist_ok=True)
        memory_file = memory_dir / "MEMORY.md"

        existing = memory_file.read_text() if memory_file.exists() else ""
        memory_file.write_text(_add_goal(existing, goal))

        agent.goals.append(goal)
        self.registry.update(agent)

    def clear_goals(self, agent_name: str) -> None:
        agent = self.get_agent(agent_name)

        memory_file = Path(agent.profile_dir) / "memories" / "MEMORY.md"
        if memory_file.exists():
            memory_file.write_text(_remove_goals_section(memory_file.read_text()))

        agent.goals = []
        self.registry.update(agent)

    # ── delegation ────────────────────────────────────────────────────────────

    def delegate_task(self, agent_name: str, message: str) -> dict:
        """
        Send a task to a sub-agent's Hermes gateway and return the response.

        Posts to the agent's OpenAI-compatible /v1/chat/completions endpoint
        and blocks until the agent replies or the 120s timeout expires.
        Raises DelegationError on network failure or non-2xx response.
        """
        agent = self.get_agent(agent_name)
        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{agent.gateway_url}/v1/chat/completions",
                    json={
                        "model": "hermes",
                        "messages": [{"role": "user", "content": message}],
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise DelegationError(
                f"Agent '{agent_name}' returned {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DelegationError(
                f"Could not reach agent '{agent_name}': {e}"
            ) from e

    def routing_candidates(self) -> list[dict]:
        """
        Return all active agents as routing candidates for the orchestrator.
        Each entry contains the name, summary, and gateway_url so the
        orchestrator can decide which agent to delegate to.
        """
        return [
            {"name": a.name, "summary": a.summary, "gateway_url": a.gateway_url}
            for a in self.registry.all_active()
        ]

    # ── helpers ───────────────────────────────────────────────────────────────

    def get_agent(self, name: str) -> Agent:
        agent = self.registry.get(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found.")
        return agent


# ── pure functions (testable without side-effects) ────────────────────────────

def _validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ValueError(
            f"Invalid agent name '{name}'. "
            "Use lowercase letters, numbers, and hyphens only (must start and end with alphanumeric)."
        )


def _add_goal(content: str, goal: str) -> str:
    line = f"- {goal}"
    if _GOALS_HEADER in content:
        # Insert the new goal line right after the last existing goal bullet,
        # or directly after the header if there are none yet.
        pattern = rf"({re.escape(_GOALS_HEADER)}\n(?:- [^\n]*\n)*)"
        replacement = lambda m: m.group(1) + line + "\n"
        updated = re.sub(pattern, replacement, content, count=1)
        return updated if updated != content else content + f"\n{line}\n"
    sep = "\n\n" if content.strip() else ""
    return f"{content}{sep}{_GOALS_HEADER}\n{line}\n"


def _remove_goals_section(content: str) -> str:
    cleaned = re.sub(
        rf"\n*{re.escape(_GOALS_HEADER)}\n(?:- [^\n]*\n)*\n?",
        "",
        content,
    )
    return cleaned.strip() + "\n" if cleaned.strip() else ""
