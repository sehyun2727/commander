from __future__ import annotations

from fastapi import APIRouter, Depends

from ...deps import get_session_factory
from . import service
from .schemas import AgentCostEntry, ProjectCostSummary, TaskCostSummary

router = APIRouter(tags=["costs"])


@router.get("/api/projects/{project_id}/costs", response_model=ProjectCostSummary)
async def get_project_costs(project_id: str, session_factory=Depends(get_session_factory)):
    month_total, by_agent = await service.summary_for_project(session_factory, project_id)
    return ProjectCostSummary(
        project_id=project_id,
        month_total_usd=month_total,
        by_agent=[AgentCostEntry(agent_id=agent_id, total_usd=total) for agent_id, total in by_agent],
    )


@router.get("/api/tasks/{task_id}/costs", response_model=TaskCostSummary)
async def get_task_costs(task_id: str, session_factory=Depends(get_session_factory)):
    total = await service.summary_for_task(session_factory, task_id)
    return TaskCostSummary(task_id=task_id, total_usd=total)
