"""Sprint 18 §5 -- plain async functions, no dedicated service DI (mirrors
`tasks/service.py` / `planning/service.py`'s "no `MemoryService` singleton
in `lifespan`" pattern, sprint-18.md §5).

`record_memory` is called once per projected event, by either the
real-time subscriber (`subscriber.py`) or the idempotent backfill
(`backfill.py`, Phase 3). `recall` is called by `PlanningOrchestrator`
when a PM turn's JSON carries a `recall_request` field (Phase 2).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...core.db_models import MemoryRecordORM
from ...core.events.base import Actor, Event
from ...core.events.contracts import build_event
from ...core.events.types import EventType
from ...core.interfaces.event_bus import EventBus
from .projection import EXTRACTORS
from .registry import CATEGORIES, MAX_KEYWORD_COUNT, MAX_RECALL_LIMIT, MAX_RECALL_LOOKBACK_DAYS, MAX_TAG_COUNT, recency_decay
from .schemas import MemoryRecord, RecallRequest, RecalledMemory

logger = logging.getLogger("commander.memory")

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")


def _to_memory_record(row: MemoryRecordORM) -> MemoryRecord:
    return MemoryRecord(
        id=row.id,
        project_id=row.project_id,
        category=row.category,
        source_event_id=row.source_event_id,
        source_task_id=row.source_task_id,
        source_specification_id=row.source_specification_id,
        title=row.title,
        content_json=row.content_json,
        tags=row.tags or [],
        keywords_text=row.keywords_text,
        created_at=row.created_at,
    )


async def record_memory(session_factory, event_bus: EventBus, event: Event) -> MemoryRecord | None:
    """Project one already-persisted event into `memory_records`, if it is
    a projected `EventType` and its extractor produces a record. Safe to
    call more than once for the same event (`UNIQUE(source_event_id)` is
    the dedup guarantee, not an app-level check-then-insert)."""
    extractor = EXTRACTORS.get(event.type)
    if extractor is None:
        return None

    async with session_factory() as session:
        extracted = await extractor(event, session)
        if extracted is None:
            return None

        row = MemoryRecordORM(
            project_id=event.project_id,
            category=extracted.category,
            source_event_id=event.id,
            source_task_id=extracted.source_task_id,
            source_specification_id=extracted.source_specification_id,
            title=extracted.title,
            content_json=extracted.content_json,
            tags=extracted.tags,
            keywords_text=extracted.keywords_text,
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.debug("memory: event %s already projected, skipping duplicate insert", event.id)
            result = await session.execute(
                select(MemoryRecordORM).where(MemoryRecordORM.source_event_id == event.id)
            )
            existing = result.scalar_one_or_none()
            return _to_memory_record(existing) if existing is not None else None

    await event_bus.publish(
        build_event(
            type=EventType.MEMORY_RECORDED,
            project_id=event.project_id,
            actor=SYSTEM_ACTOR,
            payload={
                "memory_id": row.id,
                "category": row.category,
                "source_event_id": event.id,
                "source_task_id": row.source_task_id,
                "source_specification_id": row.source_specification_id,
            },
            reason=f"Projected {row.category} from event {event.id[:8]}",
        )
    )
    return _to_memory_record(row)


async def recall(session_factory, project_id: str, request: RecallRequest) -> list[RecalledMemory]:
    """Deterministic keyword/tag/recency recall (sprint-18.md §4.9). Every
    `registry.MAX_RECALL_*` ceiling is enforced here regardless of what
    `request` asks for -- `RecallRequest`'s own validators already clamp
    most fields, but this is the actual enforcement point."""
    if request.categories is not None and not request.categories:
        return []
    categories = request.categories if request.categories is not None else list(CATEGORIES)
    categories = [c for c in categories if c in CATEGORIES]
    if not categories:
        return []

    limit = max(1, min(request.limit, MAX_RECALL_LIMIT))
    since_days = min(request.since_days, MAX_RECALL_LOOKBACK_DAYS) if request.since_days is not None else MAX_RECALL_LOOKBACK_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    tags = request.tags[:MAX_TAG_COUNT]
    keywords = request.keywords[:MAX_KEYWORD_COUNT]

    async with session_factory() as session:
        result = await session.execute(
            select(MemoryRecordORM).where(
                MemoryRecordORM.project_id == project_id,
                MemoryRecordORM.category.in_(categories),
                MemoryRecordORM.created_at >= cutoff,
            )
        )
        rows = result.scalars().all()

    now = datetime.now(timezone.utc)
    scored: list[tuple[float, MemoryRecordORM]] = []
    for row in rows:
        row_tags = set(row.tags or [])
        tag_matches = sum(1 for t in tags if t in row_tags)
        keywords_text = row.keywords_text or ""
        keyword_matches = sum(1 for k in keywords if k in keywords_text)
        age_days = (now - row.created_at).total_seconds() / 86400.0
        decay = recency_decay(age_days)
        score = (tag_matches + keyword_matches) * decay if (tags or keywords) else decay
        if score <= 0:
            continue
        scored.append((score, row))

    scored.sort(key=lambda pair: (-pair[0], -pair[1].created_at.timestamp(), pair[1].id))

    return [
        RecalledMemory(
            id=row.id,
            category=row.category,
            title=row.title,
            tags=row.tags or [],
            created_at=row.created_at,
            preview=str((row.content_json or {}).get("preview", ""))[:300],
        )
        for _, row in scored[:limit]
    ]
