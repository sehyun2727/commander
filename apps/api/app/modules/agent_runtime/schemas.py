from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ...core.contracts import AgentProfile


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    role: str
    name: str
    profile: AgentProfile
    avatar_color: str
    state: str
    current_task_id: str | None
    created_at: datetime
