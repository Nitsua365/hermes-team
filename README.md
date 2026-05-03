# hermes-team

A generic framework for building, running, and managing an orchestrated team of [Hermes](https://hermes-agent.nousresearch.com) agents. One orchestrator coordinates many specialists — delegate tasks, synthesise results, and give agents standing goals that persist across every conversation.

---

## How it works

```
you  ──▶  orchestrator  ──▶  specialist agents (each in its own container)
                │                      │
                └──────────────────────┘
                    results + learnings
```

- The **orchestrator** is the only agent you talk to. It never answers directly — it routes to the right specialist(s) and returns a lossless synthesis.
- Each **sub-agent** is a fully isolated Hermes profile running in its own Docker container. It has its own memory, skills, tools, and session history.
- **Goals** written to a sub-agent persist in their Hermes memory file and are injected into every session automatically — no restart needed.
- The orchestrator can **create new agents and extend existing ones** at runtime by writing tools and skills directly into their profile directories.

---

## Requirements

- Python 3.11+
- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- [uv](https://docs.astral.sh/uv/) (or pip)

---

## Installation

```bash
git clone <this-repo>
cd hermes-team

uv pip install -e .
```

The `orchestrator` command is now available in your shell.

---

## Quickstart

```bash
# 1. Start the orchestrator (builds the image, runs Hermes setup on first launch)
orchestrator start

# 2. Add your first specialist
orchestrator agent add trend-analyst \
  --summary "Identifies macro trends from economic, social, and market data"

# 3. Give them a standing goal
orchestrator agent goal set trend-analyst "Monitor CPI and jobs data weekly and flag anomalies"

# 4. Chat with the orchestrator
orchestrator chat
```

---

## CLI reference

### `orchestrator start`

Builds the Docker image, starts the orchestrator container via Docker Compose, and runs interactive Hermes setup on first launch. Subsequent calls are idempotent — setup is skipped once the profile is initialised.

```bash
orchestrator start
```

---

### `orchestrator chat`

Opens the orchestrator's Hermes gateway UI in your browser (`http://localhost:8642` by default).

```bash
orchestrator chat
```

---

### `orchestrator agent add <name>`

Spins up a new sub-agent container, registers it in `registry.json`, and prints the command to run Hermes profile setup.

```bash
orchestrator agent add research-west
# prompts: One-line summary (used by orchestrator for routing)
```

Or pass the summary inline:

```bash
orchestrator agent add research-west --summary "Tracks western market trends and competitor moves"
```

After adding, initialise the agent's Hermes profile:

```bash
docker run -it --rm -v $(pwd)/agents/research-west:/opt/data nousresearch/hermes-agent:latest setup
```

**Name rules:** lowercase letters, numbers, and hyphens only. Must start and end with an alphanumeric character.

---

### `orchestrator agent remove <name>`

Stops the agent's container and archives its full profile directory to `agents/.archive/<name>`. Nothing is permanently deleted — the agent can be recovered later.

```bash
orchestrator agent remove research-west
# confirms before acting
```

---

### `orchestrator agent recover <name>`

Restores an archived agent's profile and restarts its container on the next available port.

```bash
orchestrator agent recover research-west
```

---

### `orchestrator agent list`

Prints a table of all active agents with their port, summary, goal count, and status.

```bash
orchestrator agent list
```

```
 Name             Summary                                   Port   Goals  Status
 trend-analyst    Identifies macro trends from economic…    8650       2  running
 research-west    Tracks western market trends and comp…    8651       1  running
```

---

### `orchestrator agent goal set <name> <goal>`

Adds a persistent goal for an agent. The goal is written to the agent's `memories/MEMORY.md` file — Hermes injects this into every session's system prompt automatically, so the goal is active from the agent's next conversation onward with no container restart required.

```bash
orchestrator agent goal set trend-analyst "Monitor CPI and jobs data weekly and flag anomalies"
orchestrator agent goal set trend-analyst "Alert on any Fed communications that shift rate expectations"
```

Goals accumulate. An agent can have as many as needed.

---

### `orchestrator agent goal list <name>`

Lists all current goals for an agent.

```bash
orchestrator agent goal list trend-analyst
```

```
Goals for trend-analyst:
  • Monitor CPI and jobs data weekly and flag anomalies
  • Alert on any Fed communications that shift rate expectations
```

---

### `orchestrator agent goal clear <name>`

Removes all goals for an agent from both the registry and their `MEMORY.md`.

```bash
orchestrator agent goal clear trend-analyst
# confirms before acting
```

---

## Configuration

Drop a `hermes-team.yaml` in the project root to override defaults:

```yaml
image: nousresearch/hermes-agent:latest
orchestrator_name: hermes-orchestrator
orchestrator_port: 8642
agent_base_port: 8650
```

All fields are optional. The file is loaded automatically when `orchestrator` runs from the same directory.

---

## Extending agents

Because the orchestrator container has the project directory mounted at `/workspace`, it can write new tools and skills directly into any sub-agent's profile. Two built-in orchestrator skills handle this:

**Give a sub-agent a new Python tool** — call capability that uses custom code, an API with auth, subprocess calls, or binary data:

> *"Give the trend-analyst agent a tool that fetches CPI data from the FRED API"*

The orchestrator follows the `create-sub-agent-tool` skill to write the tool file to `agents/trend-analyst/tools/fred_cpi.py`, then tells you to run `docker restart trend-analyst`.

**Give a sub-agent a new skill** — instructional workflow using existing Hermes tools and shell commands:

> *"Teach the research-west agent how to summarise a competitor's pricing page weekly"*

The orchestrator follows the `create-sub-agent-skill` skill to write a `SKILL.md` to `agents/research-west/skills/competitor-pricing/SKILL.md`.

---

## Extending the orchestrator

The `tools/` and `skills/` directories in this repo are baked into the orchestrator Docker image at build time. The container's `entrypoint.sh` syncs them into the live profile on every start (no-overwrite, so your customisations are safe).

**Add a new orchestrator tool** (Python):

```bash
# tools/my_tool.py
docker compose build && docker compose up -d
```

**Add a new orchestrator skill** (Hermes SKILL.md):

```bash
mkdir skills/my-skill
# write skills/my-skill/SKILL.md
docker compose build && docker compose up -d
```

---

## Running tests

```bash
uv pip install -e ".[dev]"
pytest
```

75 tests covering agent lifecycle, goal management, registry persistence, and all CLI commands.

---

## Project layout

```
orchestrator/        Python package — AgentManager, registry, Docker client, CLI
tools/               Python tools loaded into the orchestrator agent
skills/              Hermes skills loaded into the orchestrator agent
tests/               pytest suite
agents/              Created at runtime — one subdirectory per active agent (git-ignored)
registry.json        Created at runtime — agent state (git-ignored)
Dockerfile           Builds the orchestrator image
docker-compose.yml   Starts the orchestrator container
hermes-team.yaml     Optional config overrides
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full system diagram and internals walkthrough.
