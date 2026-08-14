from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_session_factory
from .registry import SKILL_TEMPLATES
from .schemas import SkillTemplateResponse

router = APIRouter(prefix="/api/projects/{project_id}/skill-templates", tags=["skill_templates"])


@router.get("", response_model=list[SkillTemplateResponse])
async def list_skill_templates(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    # Static, server-owned catalog (Sprint 11 §6.3) -- no per-project state,
    # so no DB lookup; every company sees the same canonical set.
    return SKILL_TEMPLATES
