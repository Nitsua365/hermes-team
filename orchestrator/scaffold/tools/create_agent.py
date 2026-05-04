"""
Orchestrator tool: create_agent

Allows the orchestrator Hermes agent to programmatically create a new
sub-agent profile so it can be assigned Kanban tasks immediately.

Use this when the team needs a new area of expertise that no existing
profile covers. The new profile is available to the Kanban dispatcher
as soon as it is created — no restart required.
"""

import json
import os
from pathlib import Path

try:
    from orchestrator.config import load_config
    from orchestrator.manager import AgentManager
    _USE_PACKAGE = True
except ImportError:
    _USE_PACKAGE = False

try:
    from hermes_tools import registry
except ImportError:
    registry = None


def check_availability() -> bool:
    return _USE_PACKAGE


def handle_create_agent(name: str, summary: str, **kwargs) -> str:
    if not _USE_PACKAGE:
        return json.dumps({"error": "orchestrator package not available"})
    try:
        config = load_config(Path(os.environ.get("PROJECT_DIR", "/workspace")))
        manager = AgentManager(config)
        agent = manager.add_agent(name, summary)
        return json.dumps({
            "status": "created",
            "name": agent.name,
            "profile_dir": agent.profile_dir,
            "next_step": (
                f"Profile '{agent.name}' is ready. "
                f"Assign Kanban tasks to '{agent.name}' to delegate work to this agent."
            ),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


schema = {
    "name": "create_agent",
    "description": (
        "Create a new sub-agent profile so it can be assigned Kanban tasks. "
        "Use this only when the team needs a specialisation that no current profile covers. "
        "After creation, assign tasks using `hermes kanban create --assignee <name>`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique agent identifier. Lowercase, hyphens only. e.g. 'trend-analyst'",
            },
            "summary": {
                "type": "string",
                "description": (
                    "One sentence describing this agent's expertise. "
                    "Be specific — this is how the orchestrator decides when to route tasks here."
                ),
            },
        },
        "required": ["name", "summary"],
    },
}

if registry:
    registry.register(schema, handle_create_agent, check_availability)
