"""
Orchestrator tool: create_agent

Allows the orchestrator Hermes agent to programmatically spin up a new
sub-agent container and register it. Call this when the team needs a new
area of expertise that no existing agent covers.

After creation, tell the user to run:
  orchestrator agent add <name>
...or run the Hermes setup manually so the agent can accept tasks.
"""

import json
import os
import subprocess
import sys

# The orchestrator container mounts the project at /workspace
sys.path.insert(0, os.environ.get("PROJECT_DIR", "/workspace"))

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
    if not _USE_PACKAGE:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def handle_create_agent(name: str, summary: str, **kwargs) -> str:
    if not _USE_PACKAGE:
        return json.dumps({"error": "orchestrator package not available at /workspace"})
    try:
        from pathlib import Path
        config = load_config(Path(os.environ.get("PROJECT_DIR", "/workspace")))
        manager = AgentManager(config)
        agent = manager.add_agent(name, summary)
        return json.dumps({
            "status": "created",
            "name": agent.name,
            "port": agent.port,
            "gateway": agent.gateway_url,
            "profile": agent.profile_dir,
            "next_step": (
                f"Ask the user to initialise the Hermes profile so the agent can accept tasks: "
                f"orchestrator agent add {agent.name}"
            ),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


schema = {
    "name": "create_agent",
    "description": (
        "Spin up a new Hermes sub-agent container and register it with the orchestrator. "
        "Use this only when the team needs new expertise that no current agent covers. "
        "After creation, prompt the user to run 'orchestrator agent add <name>' to initialise the Hermes profile."
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
