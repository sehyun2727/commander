from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.contracts import AgentProfile
from ...deps import get_event_bus, get_session_factory
from . import service
from .schemas import ProfileUpdateRequest
from .service import InvalidModelRefError

router = APIRouter(prefix="/api/agents/{agent_id}/profile", tags=["agent_profiles"])


@router.get("", response_model=AgentProfile)
async def get_profile(agent_id: str, session_factory=Depends(get_session_factory)):
    try:
        return await service.get_profile(session_factory, agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Employee not found")


@router.put("", response_model=AgentProfile)
async def update_profile(
    agent_id: str,
    body: ProfileUpdateRequest,
    session_factory=Depends(get_session_factory),
    event_bus=Depends(get_event_bus),
):
    try:
        return await service.update_profile(
            session_factory, event_bus, agent_id, body.model_dump(exclude_unset=True)
        )
    except InvalidModelRefError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError:
        raise HTTPException(status_code=404, detail="Employee not found")
