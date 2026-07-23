from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.config import settings
from ...deps import get_agent_runtime, get_event_bus, get_secrets, get_session_factory
from . import service
from .schemas import CompanySettingsRequest, ProjectCreateRequest, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreateRequest,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    session_factory=Depends(get_session_factory),
):
    project = await service.create_project(
        session_factory, event_bus, agent_runtime, body.name, settings.commander_provider
    )
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session_factory=Depends(get_session_factory)):
    return await service.list_projects(session_factory)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, session_factory=Depends(get_session_factory)):
    project = await service.get_project(session_factory, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return project


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: str,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
):
    project = await service.archive_project(session_factory, event_bus, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return project


@router.patch("/{project_id}/settings", response_model=ProjectResponse)
async def update_settings(
    project_id: str,
    body: CompanySettingsRequest,
    event_bus=Depends(get_event_bus),
    secrets=Depends(get_secrets),
    session_factory=Depends(get_session_factory),
):
    project = await service.update_settings(
        session_factory, event_bus, secrets, project_id, body.name, body.provider, body.anthropic_api_key
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return project
