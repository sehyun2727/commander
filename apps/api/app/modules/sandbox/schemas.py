from __future__ import annotations

from pydantic import BaseModel


class CapabilityResponse(BaseModel):
    execution: bool
    reason: str | None = None


class ExecutionSettingsResponse(BaseModel):
    execution_available: bool
    reason: str | None = None
    execution_enabled: bool


class SetExecutionEnabledRequest(BaseModel):
    enabled: bool
