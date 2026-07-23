from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    period_start: datetime
    period_end: datetime
    summary_markdown: str
    generated_at: datetime
