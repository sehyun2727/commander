"""Structural contract an event must satisfy, independent of implementation.

Anything satisfying this Protocol can flow through the Event Bus even if it
doesn't inherit from Event (e.g. a value rehydrated from storage). Kept
separate from Event so consumers can depend on shape, not a base class.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .types import EventType


@runtime_checkable
class EventLike(Protocol):
    type: EventType
    id: str
    created_at: datetime
