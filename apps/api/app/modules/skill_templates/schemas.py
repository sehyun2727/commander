from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SkillTemplateResponse(BaseModel):
    """Read-only, CEO-facing view of a skill template -- deliberately
    excludes `capabilities`, which is internal/inert presentation data,
    not something the client should treat as an executable grant list."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    title: str
    description: str
