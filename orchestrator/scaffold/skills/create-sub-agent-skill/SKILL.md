---
name: create-sub-agent-skill
description: Write a new SKILL.md into a sub-agent's profile to give them new instructional capabilities on next restart
version: 1.0.0
author: orchestrator
license: MIT
requires_toolsets:
  - terminal
  - file
---

# Create Sub-Agent Skill

Use this skill when a sub-agent needs a new capability that can be expressed as instructions + existing hermes tools + shell commands. Skills require no custom Python and are faster to create than tools.

If the capability needs custom Python code, subprocess calls, or binary data handling, create a Tool instead (see `create-sub-agent-tool`).

## Quick Reference

- Skill directories live at: `/workspace/agents/<agent-name>/skills/<skill-name>/`
- Each skill needs exactly one `SKILL.md` inside that directory
- Optional helper scripts go in: `/workspace/agents/<agent-name>/skills/<skill-name>/scripts/`
- Sub-agent must be restarted after writing: `docker restart <agent-name>`
- Skill names must be lowercase and hyphenated — no spaces, no underscores

## Procedure

1. Confirm the target agent name and verify it exists: `ls /workspace/agents/`

2. Determine the skill name (lowercase-hyphenated), a one-line description, and the workflow the skill should teach the agent.

3. Create the skill directory:
   ```
   mkdir -p /workspace/agents/<agent-name>/skills/<skill-name>
   ```

4. Write `/workspace/agents/<agent-name>/skills/<skill-name>/SKILL.md` using this structure:

```markdown
---
name: <skill-name>
description: <one sentence — what the agent does with this skill>
version: 1.0.0
author: orchestrator
license: MIT
---

# <Skill Name>

<One paragraph of context: when to use this skill and why it matters for this agent's role.>

## Quick Reference

- <key fact or command>
- <key fact or command>

## Procedure

1. <First step — be concrete, name the tools or commands to use>
2. <Second step>
3. <Continue until the task is complete>

## Verification

- <How to confirm the skill worked correctly>

## Pitfalls

- <Common mistake and how to avoid it>
```

5. If the skill needs helper scripts (complex parsing, multi-step shell logic), add them to a `scripts/` subdirectory and reference them from the skill body.

6. Restart the sub-agent container so it loads the new skill:
   ```
   docker restart <agent-name>
   ```

7. Confirm the skill loaded:
   ```
   docker logs <agent-name> --tail 20
   ```

## Pitfalls

- Skills teach the agent HOW to do something — don't restate things hermes already knows natively
- Keep the procedure section concrete: name the actual tools, shell commands, or APIs to use
- Overly long skills hurt routing accuracy; aim for under 150 lines total
- Skills cannot add new Python code — if the agent needs a new function, use `create-sub-agent-tool` instead
- After writing, always restart the container — skills are not hot-reloaded
