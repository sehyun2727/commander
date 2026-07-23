"""Event contracts: the shape of every fact that flows through the Event Bus.

Pure data — no persistence, no dispatch logic. See core.interfaces.event_bus
for the pub/sub contract that moves these events around.
"""

from .base import Event
from .interface import EventLike
from .types import EventType

__all__ = ["Event", "EventType", "EventLike"]
