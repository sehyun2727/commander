from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...deps import get_event_bus, get_secrets, get_session_factory
from . import service
from .schemas import ReportResponse

router = APIRouter(tags=["reports"])


@router.post("/api/projects/{project_id}/reports/generate", response_model=ReportResponse)
async def generate_report(
    project_id: str,
    secrets=Depends(get_secrets),
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
):
    report = await service.generate_report(session_factory, secrets, event_bus, project_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return report


@router.get("/api/projects/{project_id}/reports", response_model=list[ReportResponse])
async def list_reports(project_id: str, session_factory=Depends(get_session_factory)):
    return await service.list_reports(session_factory, project_id)


@router.get("/api/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, session_factory=Depends(get_session_factory)):
    report = await service.get_report(session_factory, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
