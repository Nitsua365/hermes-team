"""
Project scaffolding: copies bundled template files into a target directory
so `orchestrator init` can bootstrap a project anywhere on the machine.
"""

import re
import shutil
import stat
from pathlib import Path

_SCAFFOLD_DIR = Path(__file__).parent

_SENTINEL = ".hermes-initialized"


def already_initialized(project_dir: Path) -> bool:
    return (project_dir / _SENTINEL).exists()


def init_project(project_dir: Path, force: bool = False) -> list[str]:
    """
    Copy scaffold files into *project_dir* and return a list of created paths.

    Raises FileExistsError if the project is already initialized and
    force=False.
    """
    if already_initialized(project_dir) and not force:
        raise FileExistsError(
            f"'{project_dir}' is already an orchestrator project. "
            "Pass --force to reinitialise."
        )

    created: list[str] = []

    # ── static files ──────────────────────────────────────────────────────────
    static = [
        "Dockerfile",
        "entrypoint.sh",
        "hermes-team.yaml",
    ]
    for name in static:
        src = _SCAFFOLD_DIR / name
        dst = project_dir / name
        if not dst.exists() or force:
            shutil.copy2(src, dst)
            if name == "entrypoint.sh":
                dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            created.append(str(dst.relative_to(project_dir)))

    # ── docker-compose.yml (rendered from template) ────────────────────────────
    compose_dst = project_dir / "docker-compose.yml"
    if not compose_dst.exists() or force:
        image_name = _slug(project_dir.name) + "-hermes"
        container_name = _slug(project_dir.name) + "-orchestrator"
        compose_dst.write_text(
            _render_compose(image_name, container_name, port=8642, profile_dir="~/.hermes-orchestrator")
        )
        created.append("docker-compose.yml")

    # ── directory trees ───────────────────────────────────────────────────────
    for tree in ("tools", "skills"):
        src_tree = _SCAFFOLD_DIR / tree
        dst_tree = project_dir / tree
        if src_tree.exists():
            _copy_tree(src_tree, dst_tree, force=force, created=created, base=project_dir)

    # ── runtime directories ───────────────────────────────────────────────────
    (project_dir / "agents").mkdir(exist_ok=True)

    # ── sentinel ──────────────────────────────────────────────────────────────
    (project_dir / _SENTINEL).touch()

    return created


# ── helpers ───────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hermes"


def _render_compose(image_name: str, container_name: str, port: int, profile_dir: str) -> str:
    template = (_SCAFFOLD_DIR / "docker-compose.yml").read_text()
    return template.format(
        image_name=image_name,
        container_name=container_name,
        port=port,
        profile_dir=profile_dir,
    )


_SKIP_SUFFIXES = {".pyc"}
_SKIP_NAMES = {"__init__.py", "__pycache__"}


def _copy_tree(src: Path, dst: Path, force: bool, created: list[str], base: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if any(part in _SKIP_NAMES for part in item.parts):
            continue
        if item.suffix in _SKIP_SUFFIXES:
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists() or force:
            shutil.copy2(item, target)
            created.append(str(target.relative_to(base)))
