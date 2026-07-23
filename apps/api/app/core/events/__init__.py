"""Event contracts: the shape of every fact that flows through the Event Bus.

Pure data — no persistence, no dispatch logic. See core.interfaces.event_bus
for the pub/sub contract that moves these events around.
"""

from .base import Actor, Event, EventKind
from .contracts import PAYLOAD_MODELS, Payload, build_event
from .interface import EventLike
from .types import EventType

__all__ = [
    "Actor",
    "Event",
    "EventKind",
    "EventType",
    "EventLike",
    "Payload",
    "PAYLOAD_MODELS",
    "build_event",
]
