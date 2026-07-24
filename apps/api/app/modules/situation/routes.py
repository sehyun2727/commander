from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...deps import get_event_bus, get_secrets, get_session_factory
from . import service
from .schemas import SituationResponse

router = APIRouter(tags=["situation"])


@router.get("/api/projects/{project_id}/situation", response_model=SituationResponse)
async def get_situation(
    project_id: str,
    secrets=Depends(get_secrets),
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
):
    result = await service.get_situation(session_factory, secrets, event_bus, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Company not found")
    text, generated_at = result
    return SituationResponse(text=text, generated_at=generated_at)
