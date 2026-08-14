from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ...core.db_models import AgentORM, ProjectORM, UserORM
from ...core.errors import SingletonRoleViolation
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_event_bus, get_session_factory
from .schemas import AgentResponse, HireEmployeeRequest
from .service import (
    InvalidEmployeeNameError,
    InvalidModelRefError,
    InvalidRoleError,
    InvalidSkillTemplateError,
    hire_employee,
)

router = APIRouter(prefix="/api/projects", tags=["agents"])


@router.get("/{project_id}/agents", response_model=list[AgentResponse])
async def list_agents(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    async with session_factory() as session:
        result = await session.execute(
            select(AgentORM).where(AgentORM.project_id == project_id).order_by(AgentORM.created_at.asc())
        )
        return list(result.scalars().all())


@router.post("/{project_id}/agents", response_model=AgentResponse, status_code=201)
async def hire_agent(
    project_id: str,
    body: HireEmployeeRequest,
    session_factory=Depends(get_session_factory),
    event_bus=Depends(get_event_bus),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
    try:
        return await hire_employee(
            session_factory,
            event_bus,
            project_id,
            project.provider,
            body.role_key,
            body.name,
            model_ref=body.model_ref,
            skill_template_key=body.skill_template_key,
        )
    except (InvalidRoleError, InvalidEmployeeNameError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (InvalidModelRefError, InvalidSkillTemplateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except SingletonRoleViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc))
