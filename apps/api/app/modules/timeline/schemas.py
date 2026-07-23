from __future__ import annotations

from pydantic import BaseModel

from ...core.events.base import Event


class TimelinePage(BaseModel):
    items: list[Event]
    next_cursor: int | None
