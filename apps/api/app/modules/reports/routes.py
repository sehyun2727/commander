from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import ReportORM, UserORM
from ...core.ownership import project_owned_by, resource_owned_by
from ...deps import get_current_user, get_event_bus, get_secrets, get_session_factory
from . import service
from .schemas import ReportResponse

router = APIRouter(tags=["reports"])


@router.post("/api/projects/{project_id}/reports/generate", response_model=ReportResponse)
async def generate_report(
    project_id: str,
    secrets=Depends(get_secrets),
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    report = await service.generate_report(session_factory, secrets, event_bus, project_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return report


@router.get("/api/projects/{project_id}/reports", response_model=list[ReportResponse])
async def list_reports(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.list_reports(session_factory, project_id)


@router.get("/api/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, ReportORM, report_id, user.id):
        raise HTTPException(status_code=404, detail="Report not found")
    report = await service.get_report(session_factory, report_id)
    return report
