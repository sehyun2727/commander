"""Base shape every Commander event must satisfy."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .types import EventType


@dataclass(frozen=True, kw_only=True)
class Event:
    """An immutable fact about something that already happened.

    Every concrete event in core.events.contracts extends this. Fields here
    are the ones every consumer (Timeline, Reports, Event Bus itself) can
    rely on regardless of event type.
    """

    type: EventType
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    project_id: str | None = None
    actor: str | None = None  # agent id, "ceo", or "system"
