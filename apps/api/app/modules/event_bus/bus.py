"""Concrete EventBus: persist -> fan out to subscribers -> push to SSE.

This is the dependency floor of the backend (see docs/backend/MODULES.md):
depends only on core.events and core.db_models, nothing else.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from sqlalchemy import select

from ...core.db_models import EventORM
from ...core.events.base import Actor, Event
from ...core.events.types import EventType
from ...core.interfaces.event_bus import EventBus, EventHandler

logger = logging.getLogger("commander.event_bus")


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


class InProcessEventBus(EventBus):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._streams: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, event: Event) -> Event:
        async with self._session_factory() as session:
            row = EventORM(
                id=event.id,
                project_id=event.project_id,
                kind=event.kind,
                type=event.type.value,
                actor_role=event.actor.role,
                actor_id=event.actor.id,
                actor_name=event.actor.name,
                payload=event.payload,
                reason=event.reason,
                created_at=event.created_at,
            )
            session.add(row)
            await session.commit()

        for handler in self._subscribers.get(event.type, []):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - a subscriber's failure must not break publish
                logger.exception("event subscriber failed for %s", event.type)

        for queue in list(self._streams.get(event.project_id, [])):
            queue.put_nowait(event)

        return event

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish_transient(self, event: Event) -> None:
        for queue in list(self._streams.get(event.project_id, [])):
            queue.put_nowait(event)

    def register_stream(self, project_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._streams[project_id].append(queue)
        return queue

    def unregister_stream(self, project_id: str, queue: asyncio.Queue) -> None:
        streams = self._streams.get(project_id, [])
        if queue in streams:
            streams.remove(queue)

    async def recent(self, project_id: str, limit: int = 50) -> list[Event]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EventORM)
                .where(EventORM.project_id == project_id)
                .order_by(EventORM.seq.desc())
                .limit(limit)
            )
            rows = list(result.scalars().all())
        rows.reverse()
        return [_event_from_row(r) for r in rows]

    async def page(
        self,
        project_id: str,
        cursor: int | None,
        limit: int,
        kind: str | None,
    ) -> tuple[list[Event], int | None]:
        """Cursor pagination for the Timeline: newest-first. `cursor` is
        the lowest `seq` already seen; passing it back walks further into
        the past (`seq < cursor`, still newest-of-page first), so the
        default call (`cursor=None`) always returns the most recent page
        and "load earlier" is a natural forward call chain."""
        async with self._session_factory() as session:
            stmt = select(EventORM).where(EventORM.project_id == project_id)
            if kind:
                stmt = stmt.where(EventORM.kind == kind)
            if cursor is not None:
                stmt = stmt.where(EventORM.seq < cursor)
            stmt = stmt.order_by(EventORM.seq.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
        next_cursor = rows[-1].seq if rows else None
        return [_event_from_row(r) for r in rows], next_cursor

    async def conversation_for(
        self, project_id: str, task_id: str | None = None, agent_id: str | None = None
    ) -> list[Event]:
        """Meeting transcript: conversation-kind events for one task or
        agent. Filtered in Python rather than via JSON-column SQL — the
        per-company event volume in this sprint's scope is small."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(EventORM)
                .where(EventORM.project_id == project_id, EventORM.kind == "conversation")
                .order_by(EventORM.seq.asc())
            )
            rows = list(result.scalars().all())
        events = [_event_from_row(r) for r in rows]
        if task_id:
            events = [e for e in events if e.payload.get("task_id") == task_id]
        if agent_id:
            events = [e for e in events if e.payload.get("agent_id") == agent_id]
        return events
