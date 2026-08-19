"""Sprint 18 Phase 3 -- one-shot idempotent backfill for Companies whose
event history predates the memory subscriber (`subscriber.py`) being
installed. Replays every already-persisted event of a projected
`EventType` through the same `record_memory` path the live subscriber
uses; safe to run repeatedly because `record_memory`'s own
`UNIQUE(source_event_id)` handling is the dedup guarantee, not anything
backfill-specific (sprint-18.md Definition of Done #17)."""

from __future__ import annotations

import logging

from sqlalchemy import select

from ...core.db_models import EventORM
from ...core.events.base import Actor, Event
from ...core.events.types import EventType
from ...core.interfaces.event_bus import EventBus
from .registry import PROJECTED_EVENT_TYPES
from .service import record_memory

logger = logging.getLogger("commander.memory")


def _event_from_row(row: EventORM) -> Event:
    return Event(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        type=EventType(row.type),
        actor=Actor(role=row.actor_role, id=row.actor_id, name=row.actor_name),
        payload=row.payload,
        reason=row.reason,
        created_at=row.created_at,
    )


async def backfill_memory(session_factory, event_bus: EventBus, *, project_id: str | None = None) -> int:
    """Project every already-persisted projected-type event into
    `memory_records`. Returns the number of events considered, not the
    number of new rows inserted -- a duplicate is silently skipped inside
    `record_memory`, so re-running this against the same events always
    reports the same count with zero net-new rows."""
    projected_types = [t.value for t in PROJECTED_EVENT_TYPES]
    async with session_factory() as session:
        stmt = select(EventORM).where(EventORM.type.in_(projected_types))
        if project_id is not None:
            stmt = stmt.where(EventORM.project_id == project_id)
        stmt = stmt.order_by(EventORM.seq.asc())
        result = await session.execute(stmt)
        rows = list(result.scalars().all())

    count = 0
    for row in rows:
        event = _event_from_row(row)
        await record_memory(session_factory, event_bus, event)
        count += 1

    scope = f"project {project_id}" if project_id else "all projects"
    logger.info("memory: backfill considered %d event(s) for %s", count, scope)
    return count
