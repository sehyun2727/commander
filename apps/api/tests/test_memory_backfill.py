"""Sprint 18 Phase 3 -- `memory.backfill_memory` idempotency and scoping
(sprint-18.md §10 Phase 3 item 6, Definition of Done #17). The harness's
own `event_bus` never has the memory subscriber installed, so events
published through it in these tests land in `events` but never in
`memory_records` until `backfill_memory` runs -- exactly the "Company
existed before the subscriber was installed" scenario the CLI targets."""

from __future__ import annotations

from sqlalchemy import select

import pytest

from app.core.db_models import MemoryRecordORM, TaskORM
from app.core.events.base import Actor
from app.core.events.contracts import build_event
from app.core.events.types import EventType
from app.modules.memory import backfill_memory
from app.modules.projects.service import create_project
from app.modules.tasks import service as tasks_service

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")


async def _make_project(harness, name="Acme"):
    return await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name, "mock", owner_id=harness.user.id
    )


async def _make_task(harness, project_id: str) -> TaskORM:
    return await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project_id, "Add search bar", "desc", "normal", deliverable_type="code"
    )


async def _all_memory_rows(harness) -> list[MemoryRecordORM]:
    async with harness.session_factory() as session:
        result = await session.execute(select(MemoryRecordORM))
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_backfill_projects_every_preexisting_projected_event(harness):
    project = await _make_project(harness)
    task_a = await _make_task(harness, project.id)
    task_b = await _make_task(harness, project.id)

    await harness.event_bus.publish(
        build_event(type=EventType.TASK_FAILED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task_a.id})
    )
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_COMPLETED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task_b.id})
    )
    # TASK_CREATED is not a projected type -- must not affect the count.
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_CREATED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task_a.id, "title": "x"})
    )

    assert await _all_memory_rows(harness) == []

    count = await backfill_memory(harness.session_factory, harness.event_bus, project_id=project.id)

    assert count == 2
    rows = await _all_memory_rows(harness)
    assert len(rows) == 2
    categories = {r.category for r in rows}
    assert categories == {"failed_attempts", "successful_solutions"}


@pytest.mark.asyncio
async def test_backfill_is_idempotent_on_rerun(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_FAILED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task.id})
    )

    first_count = await backfill_memory(harness.session_factory, harness.event_bus, project_id=project.id)
    second_count = await backfill_memory(harness.session_factory, harness.event_bus, project_id=project.id)

    assert first_count == 1
    assert second_count == 1
    rows = await _all_memory_rows(harness)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_backfill_without_project_id_covers_all_companies(harness):
    project_a = await _make_project(harness, name="Acme A")
    project_b = await _make_project(harness, name="Acme B")
    task_a = await _make_task(harness, project_a.id)
    task_b = await _make_task(harness, project_b.id)
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_FAILED, project_id=project_a.id, actor=SYSTEM_ACTOR, payload={"task_id": task_a.id})
    )
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_FAILED, project_id=project_b.id, actor=SYSTEM_ACTOR, payload={"task_id": task_b.id})
    )

    count = await backfill_memory(harness.session_factory, harness.event_bus, project_id=None)

    assert count == 2
    rows = await _all_memory_rows(harness)
    assert {r.project_id for r in rows} == {project_a.id, project_b.id}


@pytest.mark.asyncio
async def test_backfill_project_id_scopes_to_one_company(harness):
    project_a = await _make_project(harness, name="Acme A")
    project_b = await _make_project(harness, name="Acme B")
    task_a = await _make_task(harness, project_a.id)
    task_b = await _make_task(harness, project_b.id)
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_FAILED, project_id=project_a.id, actor=SYSTEM_ACTOR, payload={"task_id": task_a.id})
    )
    await harness.event_bus.publish(
        build_event(type=EventType.TASK_FAILED, project_id=project_b.id, actor=SYSTEM_ACTOR, payload={"task_id": task_b.id})
    )

    count = await backfill_memory(harness.session_factory, harness.event_bus, project_id=project_a.id)

    assert count == 1
    rows = await _all_memory_rows(harness)
    assert len(rows) == 1
    assert rows[0].project_id == project_a.id
