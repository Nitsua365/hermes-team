"""
Orchestrator tool: list_profiles

Returns all registered sub-agent profiles with their names and specialisations.
The orchestrator calls this when building a Kanban DAG so it knows which agents
are available and what each one is best suited to handle.
"""

import json
import os
from pathlib import Path

try:
    from hermes_tools import registry
except ImportError:
    registry = None


def check_availability() -> bool:
    return True


def handle_list_profiles(**kwargs) -> str:
    try:
        workspace = Path(os.environ.get("PROJECT_DIR", "/workspace"))
        registry_file = workspace / "registry.json"

        if not registry_file.exists():
            return json.dumps({
                "profiles": [],
                "hint": "No agents registered yet. Use `orchestrator agent add <name>` on the host to add agents.",
            })

        data = json.loads(registry_file.read_text())
        profiles = [
            {
                "name": name,
                "summary": agent["summary"],
                "goals": agent.get("goals", []),
            }
            for name, agent in data.get("active", {}).items()
        ]

        return json.dumps({"profiles": profiles})
    except Exception as e:
        return json.dumps({"error": str(e)})


schema = {
    "name": "list_profiles",
    "description": (
        "List all registered sub-agent profiles with their names and specialisations. "
        "Call this before building a task DAG to know which agents are available "
        "and what each one is best suited to handle. "
        "Only assign Kanban tasks to profiles that appear in this list."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

if registry:
    registry.register(schema, handle_list_profiles, check_availability)
