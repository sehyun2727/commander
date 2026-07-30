from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_event_bus, get_session_factory
from .schemas import TimelinePage

router = APIRouter(prefix="/api/projects", tags=["timeline"])


@router.get("/{project_id}/events", response_model=TimelinePage)
async def get_events(
    project_id: str,
    cursor: int | None = None,
    limit: int = 50,
    kind: Literal["system", "conversation"] | None = None,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    items, next_cursor = await event_bus.page(project_id, cursor, limit, kind)
    return TimelinePage(items=items, next_cursor=next_cursor)
