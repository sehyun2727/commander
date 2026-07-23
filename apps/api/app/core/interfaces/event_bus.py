"""Port: how the rest of the system publishes and subscribes to events.

Concrete implementation lives in modules/event_bus. Nothing outside this
module may depend on a specific event bus implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from ..events.base import Event

EventHandler = Callable[[Event], None]


class EventBus(ABC):
    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publish an event. Must not raise for handler failures — that is
        the handler's own concern, not the bus's."""

    @abstractmethod
    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        """Register a handler to run whenever an event of event_type is
        published."""
