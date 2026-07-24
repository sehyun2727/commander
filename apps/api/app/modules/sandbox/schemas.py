from __future__ import annotations

from pydantic import BaseModel


class CapabilityResponse(BaseModel):
    execution: bool
    reason: str | None = None
