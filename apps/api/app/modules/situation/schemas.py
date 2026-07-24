from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SituationResponse(BaseModel):
    text: str
    generated_at: datetime
