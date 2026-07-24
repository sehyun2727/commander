from __future__ import annotations

import pytest

from app.core.events import Actor, EventType, build_event

CEO = Actor(role="ceo", id="ceo", name="CEO")


@pytest.mark.asyncio
async def test_publish_persists_and_recent_returns_it_in_order(harness):
    first = await harness.event_bus.publish(
        build_event(type=EventType.PROJECT_CREATED, project_id="p1", actor=CEO, payload={"name": "Acme"}, reason="founded")
    )
    second = await harness.event_bus.publish(
        build_event(
            type=EventType.TASK_CREATED,
            project_id="p1",
            actor=CEO,
            payload={"task_id": "t1", "title": "Add search bar"},
            reason="created",
        )
    )

    recent = await harness.event_bus.recent("p1")
    assert [e.id for e in recent] == [first.id, second.id]


@pytest.mark.asyncio
async def test_recent_is_scoped_per_project(harness):
    await harness.event_bus.publish(
        build_event(type=EventType.PROJECT_CREATED, project_id="p1", actor=CEO, payload={"name": "Acme"}, reason="")
    )
    await harness.event_bus.publish(
        build_event(type=EventType.PROJECT_CREATED, project_id="p2", actor=CEO, payload={"name": "Globex"}, reason="")
    )

    assert len(await harness.event_bus.recent("p1")) == 1
    assert len(await harness.event_bus.recent("p2")) == 1


@pytest.mark.asyncio
async def test_page_pagination_advances_the_cursor(harness):
    for i in range(3):
        await harness.event_bus.publish(
            build_event(
                type=EventType.TASK_CREATED,
                project_id="p1",
                actor=CEO,
                payload={"task_id": f"t{i}", "title": f"Mission {i}"},
                reason="",
            )
        )

    page1, cursor1 = await harness.event_bus.page("p1", cursor=None, limit=2, kind=None)
    assert len(page1) == 2
    assert cursor1 is not None
    # Newest-first: the default (no cursor) page is the two most recent
    # events, t2 then t1 -- not the oldest, so a CEO opening the Timeline
    # sees current activity without paging through history first.
    assert [e.payload["task_id"] for e in page1] == ["t2", "t1"]

    page2, cursor2 = await harness.event_bus.page("p1", cursor=cursor1, limit=2, kind=None)
    assert len(page2) == 1
    assert cursor2 is not None
    assert page2[0].payload["task_id"] == "t0"


@pytest.mark.asyncio
async def test_conversation_for_filters_by_task(harness):
    await harness.event_bus.publish(
        build_event(
            type=EventType.CONVERSATION_MESSAGE,
            project_id="p1",
            actor=CEO,
            payload={"text": "hi", "task_id": "t1"},
        )
    )
    await harness.event_bus.publish(
        build_event(
            type=EventType.CONVERSATION_MESSAGE,
            project_id="p1",
            actor=CEO,
            payload={"text": "unrelated", "task_id": "t2"},
        )
    )

    messages = await harness.event_bus.conversation_for("p1", task_id="t1")
    assert len(messages) == 1
    assert messages[0].payload["text"] == "hi"


@pytest.mark.asyncio
async def test_a_failing_subscriber_does_not_break_publish(harness):
    async def boom(_event):
        raise RuntimeError("subscriber exploded")

    harness.event_bus.subscribe(EventType.PROJECT_CREATED, boom)

    event = await harness.event_bus.publish(
        build_event(type=EventType.PROJECT_CREATED, project_id="p1", actor=CEO, payload={"name": "Acme"}, reason="")
    )
    assert event is not None
    assert len(await harness.event_bus.recent("p1")) == 1
