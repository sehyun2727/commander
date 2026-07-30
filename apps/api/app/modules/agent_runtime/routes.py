from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ...core.db_models import AgentORM, UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_session_factory
from .schemas import AgentResponse

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
