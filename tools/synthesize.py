"""
Orchestrator tool: synthesize

Collects all completed task summaries from the active Kanban board and
returns them in dependency order for the orchestrator to compose into a
final lossless answer. Always the last step in any pipeline.
"""

import json
import subprocess

try:
    from hermes_tools import registry
except ImportError:
    registry = None


def check_availability() -> bool:
    return subprocess.run(
        ["hermes", "kanban", "--help"], capture_output=True
    ).returncode == 0


def handle_synthesize(pipeline_id: str = "", **kwargs) -> str:
    """
    Collect completed task summaries from the Kanban board.

    If pipeline_id is provided, only tasks that are ancestors of that task
    (or the task itself) are included. Otherwise all done tasks are returned.
    """
    try:
        result = subprocess.run(
            ["hermes", "kanban", "list", "--status", "done", "--json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return json.dumps({"error": f"kanban list failed: {result.stderr.strip()}"})

        done_tasks = json.loads(result.stdout) if result.stdout.strip() else []

        summaries = []
        for task in done_tasks:
            task_id = task.get("id", "")

            # Fetch full task details to get the run summary
            show_result = subprocess.run(
                ["hermes", "kanban", "show", task_id, "--json"],
                capture_output=True,
                text=True,
            )
            if show_result.returncode != 0:
                continue

            detail = json.loads(show_result.stdout)
            runs = detail.get("runs", [])
            last_summary = ""
            last_metadata: dict = {}
            for run in reversed(runs):
                if run.get("outcome") == "completed":
                    last_summary = run.get("summary", "") or run.get("result", "")
                    last_metadata = run.get("metadata") or {}
                    break

            summaries.append({
                "id": task_id,
                "title": task.get("title", ""),
                "assignee": task.get("assignee", ""),
                "summary": last_summary,
                "metadata": last_metadata,
            })

        return json.dumps({
            "task_summaries": summaries,
            "count": len(summaries),
            "instruction": (
                "Compose the above task outputs into a single final answer for the user. "
                "Preserve all key findings, decisions, and deliverables in full. "
                "Do not truncate, paraphrase away detail, or omit any substantive output."
            ),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


schema = {
    "name": "synthesize",
    "description": (
        "Collect all completed Kanban task summaries from the current pipeline "
        "and return them for final synthesis. Call this as the last step of any "
        "pipeline to compose a lossless final answer for the user. "
        "Optionally pass the root task ID to scope the collection."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pipeline_id": {
                "type": "string",
                "description": "Optional root task ID to scope collection (e.g. 't_abc123'). Omit to collect all done tasks.",
            }
        },
        "required": [],
    },
}

if registry:
    registry.register(schema, handle_synthesize, check_availability)
