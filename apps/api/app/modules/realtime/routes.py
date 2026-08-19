"""SSE realtime module.

Single endpoint the dashboard subscribes to per company: replays the last
50 events on connect, then streams live ones as they're published, with a
15s heartbeat so idle connections/proxies don't time out.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_event_bus, get_session_factory

router = APIRouter(prefix="/api/events", tags=["realtime"])

HEARTBEAT_SECONDS = 15


@router.get("/stream")
async def stream(
    project_id: str,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    queue = event_bus.register_stream(project_id)

    async def event_generator():
        # Sprint 19 §4.8 load-smoke finding: do NOT poll
        # `request.is_disconnected()` here. `EventSourceResponse` already
        # runs its own `_listen_for_disconnect` task that is the sole
        # intended consumer of this connection's ASGI `receive()` channel
        # (sse_starlette/sse.py); a second concurrent caller of `receive()`
        # races it for the one-shot `http.disconnect` message, and whichever
        # task loses waits forever -- reproduced as 3 concurrent SSE
        # connections deadlocking before headers were even sent. Disconnect
        # is handled solely by `EventSourceResponse` cancelling this
        # generator's task, which still runs `finally` below.
        try:
            for event in await event_bus.recent(project_id, limit=50):
                yield {"event": "commander-event", "data": event.model_dump_json()}

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield {"event": "commander-event", "data": event.model_dump_json()}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            event_bus.unregister_stream(project_id, queue)

    return EventSourceResponse(event_generator())
