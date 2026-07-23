from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    comment: str | None = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    task_id: str
    subject: str
    status: str
    comment: str | None
    created_at: datetime
    decided_at: datetime | None
