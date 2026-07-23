"""Port: how the rest of the system publishes and subscribes to events.

Concrete implementation lives in modules/event_bus. Nothing outside this
module may depend on a specific event bus implementation. Sprint 3 makes
this async: publish persists to the events table, fans out to in-process
subscribers, and pushes to any live SSE queues — all of which are I/O.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from ..events.base import Event
from ..events.types import EventType

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: Event) -> Event:
        """Persist, then fan out to subscribers and SSE listeners. Must not
        raise for handler failures — that is the handler's own concern."""

    @abstractmethod
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler to run whenever an event of event_type is
        published."""
