import platform
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import load_config
from .docker import DockerError
from .manager import AgentManager
from .scaffold import already_initialized, init_project

console = Console()
err_console = Console(stderr=True)


def _manager() -> AgentManager:
    return AgentManager(load_config(Path.cwd()))


def _require_init() -> None:
    if not already_initialized(Path.cwd()):
        err_console.print(
            "[red]Error:[/red] No orchestrator project found in the current directory.\n"
            "Run [bold]orchestrator init[/bold] first."
        )
        sys.exit(1)


# ── root ──────────────────────────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """Orchestrate a team of Hermes agents."""


# ── init ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--force", is_flag=True, default=False, help="Overwrite existing files.")
def init(force: bool) -> None:
    """Scaffold a new orchestrator project in the current directory."""
    project_dir = Path.cwd()
    try:
        created = init_project(project_dir, force=force)
    except FileExistsError as e:
        err_console.print(f"[yellow]Warning:[/yellow] {e}")
        sys.exit(1)

    console.print(f"\n[green]✓[/green] Initialised orchestrator project in [bold]{project_dir}[/bold]\n")
    for path in created:
        console.print(f"  [dim]created[/dim]  {path}")

    console.print(
        f"\n[bold]Next steps:[/bold]\n"
        f"  1. [cyan]orchestrator start[/cyan]         — build the image and launch the orchestrator\n"
        f"  2. [cyan]orchestrator chat[/cyan]           — open the Hermes UI in your browser\n"
        f"  3. [cyan]orchestrator agent add <name>[/cyan] — register a sub-agent profile\n"
    )


# ── orchestrator ──────────────────────────────────────────────────────────────

@cli.command()
def start() -> None:
    """Build and start the orchestrator. Runs Hermes setup on first launch."""
    _require_init()
    m = _manager()
    try:
        console.print("[bold]Building and starting orchestrator...[/bold]")
        m.start_orchestrator()
        console.print(
            f"[green]✓[/green] Orchestrator running at "
            f"[bold]http://localhost:{m.config.orchestrator_port}[/bold]"
        )
    except DockerError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
def chat() -> None:
    """Open the orchestrator Hermes UI in the browser."""
    m = _manager()
    url = f"http://localhost:{m.config.orchestrator_port}"
    console.print(f"Opening [bold]{url}[/bold]")
    if platform.system() == "Darwin":
        subprocess.run(["open", url])
    elif platform.system() == "Linux":
        subprocess.run(["xdg-open", url])
    else:
        console.print(f"Navigate to: {url}")


# ── agent ──────────────────────────────────────────────────────────────────────

@cli.group()
def agent() -> None:
    """Manage sub-agent profiles."""


@agent.command("add")
@click.argument("name")
@click.option(
    "--summary", "-s",
    prompt="One-line summary (used by orchestrator for routing)",
    help="What this agent specialises in.",
)
def agent_add(name: str, summary: str) -> None:
    """Create a new sub-agent profile and register it."""
    _require_init()
    m = _manager()
    try:
        a = m.add_agent(name, summary)
    except (ValueError, OSError) as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    console.print(f"\n[green]✓[/green] Agent profile [bold]{a.name}[/bold] created")
    console.print(f"  Profile : {a.profile_dir}")
    console.print(f"  Skill   : kanban-worker installed")
    console.print(
        f"\nThe dispatcher will spawn [bold]{a.name}[/bold] automatically "
        f"when a Kanban task is assigned to it.\n"
        f"Run [cyan]orchestrator chat[/cyan] to tell the orchestrator about this new team member."
    )


@agent.command("remove")
@click.argument("name")
@click.confirmation_option(prompt="Archive this agent's profile?")
def agent_remove(name: str) -> None:
    """Archive a sub-agent profile (recoverable)."""
    m = _manager()
    try:
        m.remove_agent(name)
    except (ValueError, OSError) as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    console.print(f"[green]✓[/green] Agent [bold]{name}[/bold] archived.")


@agent.command("recover")
@click.argument("name")
def agent_recover(name: str) -> None:
    """Restore an archived agent profile."""
    m = _manager()
    try:
        a = m.recover_agent(name)
    except (ValueError, OSError) as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    console.print(f"[green]✓[/green] Agent [bold]{a.name}[/bold] restored at {a.profile_dir}")


@agent.command("list")
def agent_list() -> None:
    """List all active agent profiles."""
    m = _manager()
    agents = m.registry.all_active()
    if not agents:
        console.print(
            "No agent profiles. Add one with: [bold]orchestrator agent add <name>[/bold]"
        )
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Summary")
    table.add_column("Goals", justify="right")
    table.add_column("Status")

    for a in agents:
        table.add_row(a.name, a.summary, str(len(a.goals)), a.status)

    console.print(table)


# ── goal ───────────────────────────────────────────────────────────────────────

@agent.group()
def goal() -> None:
    """Manage persistent goals for a sub-agent.

    Goals are written to the agent's MEMORY.md and injected into every Hermes
    session automatically — no restart required.
    """


@goal.command("set")
@click.argument("agent_name")
@click.argument("goal_text")
def goal_set(agent_name: str, goal_text: str) -> None:
    """Add a persistent goal for AGENT_NAME."""
    m = _manager()
    try:
        m.set_goal(agent_name, goal_text)
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    console.print(f"[green]✓[/green] Goal set for [bold]{agent_name}[/bold]: {goal_text}")


@goal.command("list")
@click.argument("agent_name")
def goal_list(agent_name: str) -> None:
    """List current goals for AGENT_NAME."""
    m = _manager()
    try:
        a = m.get_agent(agent_name)
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if not a.goals:
        console.print(f"No goals set for [bold]{agent_name}[/bold].")
        return

    console.print(f"[bold]Goals for {agent_name}:[/bold]")
    for g in a.goals:
        console.print(f"  • {g}")


@goal.command("clear")
@click.argument("agent_name")
@click.confirmation_option(prompt="Clear all goals for this agent?")
def goal_clear(agent_name: str) -> None:
    """Remove all goals for AGENT_NAME."""
    m = _manager()
    try:
        m.clear_goals(agent_name)
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    console.print(f"[green]✓[/green] Goals cleared for [bold]{agent_name}[/bold].")
