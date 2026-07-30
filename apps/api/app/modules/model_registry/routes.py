from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_event_bus, get_session_factory
from . import service
from .schemas import ModelCatalogEntry, SetModelRequest

router = APIRouter(prefix="/api/projects/{project_id}/models", tags=["model_registry"])


@router.get("", response_model=list[ModelCatalogEntry])
async def get_models(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    provider = await service.provider_for(session_factory, project_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.list_catalog(session_factory, provider, project_id)


@router.put("/{role}", response_model=ModelCatalogEntry)
async def set_model(
    project_id: str,
    role: str,
    body: SetModelRequest,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    provider = await service.provider_for(session_factory, project_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        await service.set_role_model(session_factory, event_bus, provider, project_id, role, body.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    catalog = await service.list_catalog(session_factory, provider, project_id)
    return next(entry for entry in catalog if entry["role"] == role)
