"""SSE realtime module.

Single endpoint the dashboard subscribes to per company: replays the last
50 events on connect, then streams live ones as they're published, with a
15s heartbeat so idle connections/proxies don't time out.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from ...deps import get_event_bus

router = APIRouter(prefix="/api/events", tags=["realtime"])

HEARTBEAT_SECONDS = 15


@router.get("/stream")
async def stream(project_id: str, request: Request, event_bus=Depends(get_event_bus)):
    queue = event_bus.register_stream(project_id)

    async def event_generator():
        try:
            for event in await event_bus.recent(project_id, limit=50):
                yield {"event": "commander-event", "data": event.model_dump_json()}

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield {"event": "commander-event", "data": event.model_dump_json()}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            event_bus.unregister_stream(project_id, queue)

    return EventSourceResponse(event_generator())
