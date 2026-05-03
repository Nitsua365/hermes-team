---
name: create-sub-agent-tool
description: Write a new Python tool into a sub-agent's profile so they gain a new callable capability on next restart
version: 1.0.0
author: orchestrator
license: MIT
requires_toolsets:
  - terminal
  - file
---

# Create Sub-Agent Tool

Use this skill when a sub-agent needs a new programmatic capability that requires custom Python: calling an external API with auth, processing binary data, running subprocesses, or any logic too complex for shell commands alone.

If the capability can be achieved with shell commands + existing hermes tools, create a Skill instead (see `create-sub-agent-skill`).

## Quick Reference

- Tool files live at: `/workspace/agents/<agent-name>/tools/<tool-name>.py`
- Sub-agent must be restarted after writing: `docker restart <agent-name>`
- Handler must return `json.dumps(...)` — never a raw dict
- Errors must be returned as `json.dumps({"error": "message"})` — never raised

## Procedure

1. Confirm the target agent name and verify it exists: `ls /workspace/agents/`

2. Determine the tool's name (snake_case), description, parameters, and handler logic based on what the sub-agent needs to do.

3. Write the tool file to `/workspace/agents/<agent-name>/tools/<tool-name>.py` using this exact structure:

```python
import json

try:
    from hermes_tools import registry
except ImportError:
    registry = None


def check_availability() -> bool:
    # Return False if a required binary or env var is missing.
    # Hermes will hide the tool from the agent when this returns False.
    return True


def handle_<tool_name>(<param>: <type>, **kwargs) -> str:
    try:
        result = {}  # build your result dict
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


schema = {
    "name": "<tool_name>",
    "description": "<what this tool does — one clear sentence>",
    "parameters": {
        "type": "object",
        "properties": {
            "<param>": {
                "type": "string",
                "description": "<what this parameter is>"
            }
        },
        "required": ["<param>"]
    }
}

if registry:
    registry.register(schema, handle_<tool_name>, check_availability)
```

4. Restart the sub-agent container so it picks up the new tool:
   ```
   docker restart <agent-name>
   ```

5. Confirm the tool loaded by checking the agent's logs:
   ```
   docker logs <agent-name> --tail 20
   ```

## Pitfalls

- The tool filename must be snake_case and match the `schema["name"]` value
- Never import from the tool file itself — only `hermes_tools` and stdlib/installed packages
- If `check_availability` returns False, hermes silently hides the tool — don't leave it hardcoded to False
- Large tool files slow agent startup; keep handlers focused on one responsibility
- After writing, always restart the container — tools are not hot-reloaded
