from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ...core.contracts import AgentProfile


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    # JSON field stays "role" (unchanged API contract, Sprint 10 §21 zero
    # behavior change) even though the ORM column is now `role_key`
    # (Sprint 10 §9.1) -- the alias is validation-only, it just tells
    # pydantic which ORM attribute to read from.
    role: str = Field(validation_alias="role_key")
    name: str
    profile: AgentProfile
    avatar_color: str
    state: str
    current_task_id: str | None
    created_at: datetime
