from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...core.contracts import CUSTOM_INSTRUCTIONS_MAX_LEN, DecisionStyle, Personality, WorkingStyle


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personality: Personality | None = None
    working_style: WorkingStyle | None = None
    decision_style: DecisionStyle | None = None
    custom_instructions: str | None = Field(default=None, max_length=CUSTOM_INSTRUCTIONS_MAX_LEN)
    model_ref: str | None = None
    skill_template_key: str | None = None
