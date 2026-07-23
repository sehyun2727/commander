from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.events import Actor, EventType, build_event
from app.modules.projects.service import create_project
from app.modules.reports.service import generate_report, get_report, list_reports

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")


@pytest.mark.asyncio
async def test_generate_report_is_quiet_when_nothing_happened(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")

    report = await generate_report(harness.session_factory, harness.secrets, harness.event_bus, project.id)

    assert report.project_id == project.id
    assert "Daily Report" in report.summary_markdown
    assert "quiet" in report.summary_markdown.lower()
    assert report.period_end - report.period_start == timedelta(hours=24)


@pytest.mark.asyncio
async def test_generate_report_reflects_missions_and_decisions(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")

    await harness.event_bus.publish(
        build_event(
            type=EventType.TASK_COMPLETED,
            project_id=project.id,
            actor=CEO_ACTOR,
            payload={"task_id": "task-1"},
            reason="CEO Decision on 'Ship the landing page'",
        )
    )
    await harness.event_bus.publish(
        build_event(
            type=EventType.APPROVAL_GRANTED,
            project_id=project.id,
            actor=CEO_ACTOR,
            payload={"approval_id": "approval-1"},
            reason="Approved",
        )
    )

    report = await generate_report(harness.session_factory, harness.secrets, harness.event_bus, project.id)

    assert "1 mission" in report.summary_markdown
    assert "1 decision" in report.summary_markdown
    assert "Ship the landing page" in report.summary_markdown


@pytest.mark.asyncio
async def test_generate_report_ignores_events_outside_the_24h_window(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")
    event = build_event(
        type=EventType.TASK_COMPLETED,
        project_id=project.id,
        actor=CEO_ACTOR,
        payload={"task_id": "task-old"},
        reason="CEO Decision on 'Old mission'",
    )
    await harness.event_bus.publish(event)

    from app.core.db_models import EventORM
    from sqlalchemy import update

    async with harness.session_factory() as session:
        await session.execute(
            update(EventORM)
            .where(EventORM.project_id == project.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=48))
        )
        await session.commit()

    report = await generate_report(harness.session_factory, harness.secrets, harness.event_bus, project.id)
    assert "quiet" in report.summary_markdown.lower()


@pytest.mark.asyncio
async def test_generate_report_returns_none_for_unknown_project(harness):
    report = await generate_report(harness.session_factory, harness.secrets, harness.event_bus, "no-such-project")
    assert report is None


@pytest.mark.asyncio
async def test_list_and_get_report(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")
    created = await generate_report(harness.session_factory, harness.secrets, harness.event_bus, project.id)

    reports = await list_reports(harness.session_factory, project.id)
    assert [r.id for r in reports] == [created.id]

    fetched = await get_report(harness.session_factory, created.id)
    assert fetched.summary_markdown == created.summary_markdown
