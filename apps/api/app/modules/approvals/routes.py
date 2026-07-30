from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import ApprovalORM, UserORM
from ...core.ownership import project_owned_by, resource_owned_by
from ...deps import get_current_user, get_session_factory, get_workflow_engine
from . import service
from .schemas import ApprovalDecisionRequest, ApprovalResponse

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalResponse])
async def list_pending(
    project_id: str | None = None,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if project_id and not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.list_pending(session_factory, project_id, owner_id=user.id)


@router.get("/history", response_model=list[ApprovalResponse])
async def list_history(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.list_all(session_factory, project_id)


@router.post("/{approval_id}/decision", response_model=ApprovalResponse)
async def decide(
    approval_id: str,
    body: ApprovalDecisionRequest,
    workflow_engine=Depends(get_workflow_engine),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, ApprovalORM, approval_id, user.id):
        raise HTTPException(status_code=404, detail="Decision not found or already made")
    approval = await service.decide(session_factory, workflow_engine, approval_id, body.decision, body.comment)
    if approval is None:
        raise HTTPException(status_code=404, detail="Decision not found or already made")
    return approval
