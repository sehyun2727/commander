from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_event_bus, get_secrets, get_session_factory
from . import service
from .schemas import SituationResponse

router = APIRouter(tags=["situation"])


@router.get("/api/projects/{project_id}/situation", response_model=SituationResponse)
async def get_situation(
    project_id: str,
    secrets=Depends(get_secrets),
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    result = await service.get_situation(session_factory, secrets, event_bus, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Company not found")
    text, generated_at = result
    return SituationResponse(text=text, generated_at=generated_at)
