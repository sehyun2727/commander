from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from ...deps import get_event_bus
from .schemas import TimelinePage

router = APIRouter(prefix="/api/projects", tags=["timeline"])


@router.get("/{project_id}/events", response_model=TimelinePage)
async def get_events(
    project_id: str,
    cursor: int | None = None,
    limit: int = 50,
    kind: Literal["system", "conversation"] | None = None,
    event_bus=Depends(get_event_bus),
):
    items, next_cursor = await event_bus.page(project_id, cursor, limit, kind)
    return TimelinePage(items=items, next_cursor=next_cursor)
