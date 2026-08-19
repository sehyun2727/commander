"""Sprint 18 §4.6 -- wires one EventBus handler per projected `EventType`.
Called once from `main.py::lifespan`, right after `event_bus` is
constructed. Handlers never raise: `InProcessEventBus.publish` already
logs-and-swallows a subscriber exception (`bus.py`), and `record_memory`
itself has no reason to raise -- a malformed payload makes the extractor
return `None`, and a duplicate insert is caught as an `IntegrityError`
inside `record_memory`.
"""

from __future__ import annotations

from ...core.events.base import Event
from ...core.interfaces.event_bus import EventBus
from .registry import PROJECTED_EVENT_TYPES
from .service import record_memory


def install_memory_subscribers(event_bus: EventBus, session_factory) -> None:
    async def _handle(event: Event) -> None:
        await record_memory(session_factory, event_bus, event)

    for event_type in PROJECTED_EVENT_TYPES:
        event_bus.subscribe(event_type, _handle)
