from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Agent(BaseModel):
    name: str
    summary: str
    port: int
    profile_dir: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "running"
    goals: list[str] = Field(default_factory=list)

    @property
    def gateway_url(self) -> str:
        return f"http://localhost:{self.port}"
