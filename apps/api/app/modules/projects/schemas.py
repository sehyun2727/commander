from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProjectCreateRequest(BaseModel):
    name: str


class CompanySettingsRequest(BaseModel):
    name: str | None = None
    provider: Literal["mock", "anthropic"] | None = None
    anthropic_api_key: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    provider: str
    archived: bool
    created_at: datetime


class StarterResponse(BaseModel):
    title: str
    description: str
