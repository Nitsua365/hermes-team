from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Agent(BaseModel):
    name: str
    summary: str
    profile_dir: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"
    goals: list[str] = Field(default_factory=list)
