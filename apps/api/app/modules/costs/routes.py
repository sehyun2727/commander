from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import TaskORM, UserORM
from ...core.ownership import project_owned_by, resource_owned_by
from ...deps import get_current_user, get_session_factory
from . import service
from .schemas import AgentCostEntry, ProjectCostSummary, TaskCostSummary

router = APIRouter(tags=["costs"])


@router.get("/api/projects/{project_id}/costs", response_model=ProjectCostSummary)
async def get_project_costs(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    month_total, by_agent = await service.summary_for_project(session_factory, project_id)
    return ProjectCostSummary(
        project_id=project_id,
        month_total_usd=month_total,
        by_agent=[AgentCostEntry(agent_id=agent_id, total_usd=total) for agent_id, total in by_agent],
    )


@router.get("/api/tasks/{task_id}/costs", response_model=TaskCostSummary)
async def get_task_costs(
    task_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    total = await service.summary_for_task(session_factory, task_id)
    return TaskCostSummary(task_id=task_id, total_usd=total)
