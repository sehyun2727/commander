"""Base shape every Commander event must satisfy.

Sprint 3 decision (see docs/DECISIONS.md): events are unified into a single
envelope (`Event`) with a JSON `payload`, matching the single event-stream
table persistence model, rather than one dataclass subclass per event type.
Per-type payload shapes still exist (see `contracts.py`) so callers get
typed construction and the TS codegen script has something concrete to
target.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .types import EventType

EventKind = Literal["system", "conversation"]
ActorRole = Literal["ceo", "employee", "system"]


class Actor(BaseModel):
    """Who performed the action this event records."""

    model_config = ConfigDict(extra="forbid")

    role: ActorRole
    id: str
    name: str


class Event(BaseModel):
    """An immutable fact about something that already happened.

    Every consumer (Timeline, EventBus, SSE stream) can rely on this shape
    regardless of `type`. `payload` holds the type-specific fields defined
    in `contracts.py`.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    kind: EventKind
    type: EventType
    actor: Actor
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
