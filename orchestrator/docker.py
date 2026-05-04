import subprocess


class DockerError(Exception):
    pass


class DockerClient:
    def setup_interactive(self, data_dir: str, image: str) -> None:
        """Run first-time Hermes setup for the orchestrator profile."""
        subprocess.run(
            ["docker", "run", "-it", "--rm", "-v", f"{data_dir}:/opt/data", image, "setup"]
        )

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
