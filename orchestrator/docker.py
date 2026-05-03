import subprocess


class DockerError(Exception):
    pass


class DockerClient:
    def run_agent(self, name: str, port: int, profile_dir: str, image: str) -> None:
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", name,
                "--restart", "unless-stopped",
                "--shm-size=1g",
                "-p", f"{port}:8642",
                "-v", f"{profile_dir}:/opt/data",
                image,
                "gateway", "run",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise DockerError(f"Failed to start '{name}': {result.stderr.strip()}")

    def stop(self, name: str) -> None:
        subprocess.run(["docker", "stop", name], capture_output=True)

    def remove(self, name: str) -> None:
        subprocess.run(["docker", "rm", name], capture_output=True)

    def exec(self, name: str, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "exec", name, *cmd],
            capture_output=True,
            text=True,
        )

    def setup_interactive(self, profile_dir: str, image: str) -> None:
        subprocess.run(
            ["docker", "run", "-it", "--rm", "-v", f"{profile_dir}:/opt/data", image, "setup"]
        )

    def is_running(self, name: str) -> bool:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        return name in result.stdout.strip().split()

    def compose_build(self, compose_file: str) -> None:
        result = subprocess.run(
            ["docker", "compose", "-f", compose_file, "build"]
        )
        if result.returncode != 0:
            raise DockerError("docker compose build failed")

    def compose_up(self, compose_file: str) -> None:
        result = subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise DockerError(f"docker compose up failed: {result.stderr.strip()}")
