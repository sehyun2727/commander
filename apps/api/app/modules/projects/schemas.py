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


class RoleResponse(BaseModel):
    """Sprint 10 §18: the Roles API's read-only, CEO-facing view of a
    Role -- deliberately excludes `contract`/`tools`/`permissions`, which
    are internal execution details, not organizational facts."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    title: str
    category: Literal["leadership", "worker"]
    singleton: bool
    description: str
