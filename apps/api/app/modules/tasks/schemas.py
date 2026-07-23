from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"


class TaskAssignRequest(BaseModel):
    agent_id: str | None = None


class MessageCreateRequest(BaseModel):
    text: str


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    description: str
    priority: str
    state: str
    attempt: int
    result_markdown: str
    created_at: datetime
    updated_at: datetime
