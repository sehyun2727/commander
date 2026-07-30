"""Read-only endpoints exposing the git workspace to the dashboard:
file tree, single-file content, and recent merges. Never executes,
imports, or evaluates workspace content -- text in, text out."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_session_factory, get_workspace_manager
from . import service
from .schemas import FileContentResponse, FileEntryResponse, MergeRecordResponse

router = APIRouter(tags=["workspace"])


@router.get("/api/projects/{project_id}/workspace/tree", response_model=list[FileEntryResponse])
async def get_tree(
    project_id: str,
    ref: str = "main",
    session_factory=Depends(get_session_factory),
    workspace_manager=Depends(get_workspace_manager),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.get_tree(session_factory, workspace_manager, project_id, ref)


@router.get("/api/projects/{project_id}/workspace/file", response_model=FileContentResponse)
async def get_file(
    project_id: str,
    path: str,
    ref: str = "main",
    session_factory=Depends(get_session_factory),
    workspace_manager=Depends(get_workspace_manager),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    content = await service.get_file(session_factory, workspace_manager, project_id, path, ref)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileContentResponse(path=path, content=content)


@router.get("/api/projects/{project_id}/workspace/merges", response_model=list[MergeRecordResponse])
async def get_merges(
    project_id: str,
    limit: int = 10,
    session_factory=Depends(get_session_factory),
    workspace_manager=Depends(get_workspace_manager),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.get_merges(session_factory, workspace_manager, project_id, limit)
