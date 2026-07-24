from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"
    deliverable_type: str = "code"


class TaskAssignRequest(BaseModel):
    agent_id: str | None = None


class MessageCreateRequest(BaseModel):
    text: str


class DiffResponse(BaseModel):
    diff_text: str
    truncated: bool


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
    deliverable_type: str
    branch_name: str | None
    code_stats: dict | None
    created_at: datetime
    updated_at: datetime
