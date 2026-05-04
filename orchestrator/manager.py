import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .agent import Agent
from .config import Config
from .docker import DockerClient
from .registry import AgentRegistry
from .scaffold import _SCAFFOLD_DIR

_GOALS_HEADER = "## Orchestrator Goals"
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$")

_ROLE_TEMPLATE = """\
## Role
{summary}

## Working Style
You are a specialist sub-agent in an orchestrated AI team. Tasks arrive via the
Kanban board. At the start of every session call kanban_show() to read the task
details and any output passed from parent tasks. Execute the work using your
available tools, then call kanban_complete() with a specific, detailed summary
so that downstream agents have everything they need to continue.
"""


class AgentManager:
    def __init__(self, config: Config):
        self.config = config
        self.docker = DockerClient()
        self.registry = AgentRegistry(config.registry_path)

    # ── orchestrator ─────────────────────────────────────────────────────────

    def start_orchestrator(self) -> None:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.config.profiles_dir.mkdir(parents=True, exist_ok=True)

        self.docker.compose_build(str(self.config.compose_file))
        self.docker.compose_up(str(self.config.compose_file))

        sentinel = self.config.data_dir / ".initialized"
        if not sentinel.exists():
            self.docker.setup_interactive(str(self.config.data_dir), self.config.image)
            sentinel.touch()

    # ── agents (profiles) ─────────────────────────────────────────────────────

    def add_agent(self, name: str, summary: str) -> Agent:
        _validate_name(name)

        if self.registry.get(name):
            raise ValueError(f"Agent '{name}' already exists.")

        profile_dir = self.config.profiles_dir / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Initialise MEMORY.md with role definition
        memories_dir = profile_dir / "memories"
        memories_dir.mkdir(exist_ok=True)
        (memories_dir / "MEMORY.md").write_text(_ROLE_TEMPLATE.format(summary=summary))

        # Install kanban-worker skill so the dispatcher can spawn this profile
        self._install_skill(profile_dir, "kanban-worker")

        agent = Agent(
            name=name,
            summary=summary,
            profile_dir=str(profile_dir),
            created_at=datetime.now(timezone.utc),
        )
        self.registry.add(agent)
        return agent

    def remove_agent(self, name: str) -> None:
        agent = self.get_agent(name)

        archive = self.config.profiles_dir / ".archive" / name
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(agent.profile_dir)), str(archive))

        self.registry.archive(name)

    def recover_agent(self, name: str) -> Agent:
        archived = self.registry.get_archived(name)
        if not archived:
            raise ValueError(f"No archive found for '{name}'.")

        archive = self.config.profiles_dir / ".archive" / name
        if not archive.exists():
            raise ValueError(f"Archive directory missing: {archive}")

        profile_dir = self.config.profiles_dir / name
        shutil.move(str(archive), str(profile_dir))

        return self.registry.restore(name, str(profile_dir))

    # ── goals ─────────────────────────────────────────────────────────────────

    def set_goal(self, agent_name: str, goal: str) -> None:
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

    # ── helpers ───────────────────────────────────────────────────────────────

    def get_agent(self, name: str) -> Agent:
        agent = self.registry.get(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found.")
        return agent

    def _install_skill(self, profile_dir: Path, skill_name: str) -> None:
        src = _SCAFFOLD_DIR / "skills" / skill_name
        dst = profile_dir / "skills" / skill_name
        if src.exists() and not dst.exists():
            shutil.copytree(str(src), str(dst))


# ── pure functions ────────────────────────────────────────────────────────────

def _validate_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise ValueError(
            f"Invalid agent name '{name}'. "
            "Use lowercase letters, numbers, and hyphens only (must start and end with alphanumeric)."
        )


def _add_goal(content: str, goal: str) -> str:
    line = f"- {goal}"
    if _GOALS_HEADER in content:
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
