"""Sprint 18 Phase 1 -- projection extractors, `record_memory` dedup, and
subscriber isolation (sprint-18.md §9 "Projection" / "Extractor safety" /
"Deduplication" / "Subscriber isolation"). Recall ranking, planning
integration, and backfill are Phase 2/3 territory and are not covered
here."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db_models import ApprovalORM, MemoryRecordORM, SpecificationORM, SpecificationTurnORM, SpecificationVersionORM, TaskORM
from app.core.events.base import Actor, Event
from app.core.events.contracts import build_event
from app.core.events.types import EventType
from app.modules.memory import service as memory_service
from app.modules.memory.subscriber import install_memory_subscribers
from app.modules.projects.service import create_project
from app.modules.tasks import service as tasks_service

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")


async def _make_project(harness):
    return await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )


async def _make_task(harness, project_id: str, **overrides) -> TaskORM:
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project_id, "Add search bar", "desc", "normal", deliverable_type="code"
    )
    if overrides:
        async with harness.session_factory() as session:
            row = await session.get(TaskORM, task.id)
            for key, value in overrides.items():
                setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
        return row
    return task


async def _make_approval(harness, project_id: str, task_id: str, **overrides) -> ApprovalORM:
    approval = ApprovalORM(project_id=project_id, task_id=task_id, subject="Ship the search bar", **overrides)
    async with harness.session_factory() as session:
        session.add(approval)
        await session.commit()
        await session.refresh(approval)
    return approval


async def _make_specification(harness, project_id: str) -> SpecificationORM:
    spec = SpecificationORM(project_id=project_id, request_text="Build a search bar")
    async with harness.session_factory() as session:
        session.add(spec)
        await session.commit()
        await session.refresh(spec)
    return spec


async def _make_specification_version(harness, specification_id: str, version: int = 1, **overrides) -> SpecificationVersionORM:
    kwargs = dict(
        specification_id=specification_id,
        version=version,
        title="Search bar specification",
        problem_statement="Users cannot find missions quickly.",
        goals=["Add a search box", "Filter by state"],
        non_goals=[],
        requirements=["Search must be case-insensitive"],
        acceptance_criteria=["Typing a query filters the mission list"],
        architecture_components=[],
        risks=[],
        dependencies=[],
        assumptions=[],
        unresolved_questions=[],
        implementation_stages=[],
    )
    kwargs.update(overrides)
    row = SpecificationVersionORM(**kwargs)
    async with harness.session_factory() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def _make_specification_turn(harness, specification_id: str, turn_index: int = 0, **overrides) -> SpecificationTurnORM:
    kwargs = dict(
        specification_id=specification_id,
        turn_index=turn_index,
        actor_role="employee",
        role_key="pm",
        kind="analysis",
        text="I recommend a simple substring filter for v1.",
    )
    kwargs.update(overrides)
    row = SpecificationTurnORM(**kwargs)
    async with harness.session_factory() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def _all_memory_rows(harness) -> list[MemoryRecordORM]:
    async with harness.session_factory() as session:
        result = await session.execute(select(MemoryRecordORM))
        return list(result.scalars().all())


# --- Projection: per category ------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type,decision",
    [
        (EventType.APPROVAL_GRANTED, "approved"),
        (EventType.APPROVAL_REJECTED, "rejected"),
        (EventType.APPROVAL_CHANGES_REQUESTED, "changes_requested"),
    ],
)
async def test_approval_decision_projects_ceo_approvals(harness, event_type, decision):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)
    approval = await _make_approval(harness, project.id, task.id, comment="Looks good to me")

    event = build_event(
        type=event_type, project_id=project.id, actor=SYSTEM_ACTOR, payload={"approval_id": approval.id}
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.category == "ceo_approvals"
    assert record.source_task_id == task.id
    assert f"decision:{decision}" in record.tags
    assert f"task:{task.id}" in record.tags
    assert record.tags and record.keywords_text


@pytest.mark.asyncio
async def test_specification_approved_projects_pm_specifications(harness):
    project = await _make_project(harness)
    spec = await _make_specification(harness, project.id)
    version = await _make_specification_version(harness, spec.id, version=1)

    event = build_event(
        type=EventType.SPECIFICATION_APPROVED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"specification_id": spec.id, "version": 1},
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.category == "pm_specifications"
    assert record.source_specification_id == spec.id
    assert record.content_json["goals"] == version.goals
    assert record.content_json["requirements"] == version.requirements
    assert record.content_json["acceptance_criteria"] == version.acceptance_criteria
    assert record.tags and record.keywords_text


@pytest.mark.asyncio
async def test_review_completed_projects_reviewer_feedback(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)
    sections = {
        "Problem": "Search was missing entirely",
        "Recommendation": "Add a debounced search box",
        "Risk": "None significant",
        "Impact": "Improves mission discovery",
    }

    event = build_event(
        type=EventType.REVIEW_COMPLETED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"task_id": task.id, "outcome": "approved", "sections": sections},
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.category == "reviewer_feedback"
    assert record.source_task_id == task.id
    for key, value in sections.items():
        assert record.content_json["sections"][key] == value
    assert "outcome:approved" in record.tags
    assert record.tags and record.keywords_text


@pytest.mark.asyncio
async def test_task_failed_with_self_correction_reason_code(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)

    event = build_event(
        type=EventType.TASK_FAILED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"task_id": task.id, "reason_code": "self_correction_exhausted"},
        reason="3 correction attempt(s) exhausted",
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.category == "failed_attempts"
    assert "reason_code:self_correction_exhausted" in record.tags
    assert f"task:{task.id}" in record.tags
    assert record.content_json["reason_code"] == "self_correction_exhausted"
    assert record.content_json["reason"] == "3 correction attempt(s) exhausted"


@pytest.mark.asyncio
async def test_task_failed_with_employee_surrender_preserves_bounded_preview(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)

    event = build_event(
        type=EventType.TASK_FAILED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"task_id": task.id, "reason_code": "employee_surrendered"},
        reason="**Unable to Complete:** the environment lacks a compiler",
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert "reason_code:employee_surrendered" in record.tags
    assert record.content_json["preview"] == "**Unable to Complete:** the environment lacks a compiler"


@pytest.mark.asyncio
async def test_task_failed_without_reason_code_uses_default(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)

    event = build_event(
        type=EventType.TASK_FAILED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task.id}
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.content_json["reason_code"] is None
    assert "no reason recorded" in record.content_json["reason"].lower()
    assert not any(tag.startswith("reason_code:") for tag in record.tags)


@pytest.mark.asyncio
async def test_task_failed_redacts_environment_like_surrender_text(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)

    event = build_event(
        type=EventType.TASK_FAILED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"task_id": task.id, "reason_code": "employee_surrendered"},
        reason="Tried to authenticate but ANTHROPIC_API_KEY=sk-ant-super-secret-value failed",
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert "sk-ant-super-secret-value" not in record.content_json["reason"]
    assert "[redacted]" in record.content_json["reason"]


@pytest.mark.asyncio
async def test_task_completed_projects_successful_solutions(harness):
    project = await _make_project(harness)
    task = await _make_task(
        harness,
        project.id,
        branch_name="mission/abcd1234",
        code_stats={"files_changed": 3, "insertions": 40, "deletions": 5},
        check_results=[
            {"name": "pytest", "status": "passed", "duration_seconds": 1.2, "output": ""},
            {"name": "lint", "status": "failed", "duration_seconds": 0.4, "output": ""},
        ],
    )

    event = build_event(
        type=EventType.TASK_COMPLETED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task.id}
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.category == "successful_solutions"
    assert record.source_task_id == task.id
    assert record.content_json["branch_name"] == "mission/abcd1234"
    assert record.content_json["code_stats"]["files_changed"] == 3
    assert record.content_json["checks_passed"] == 1
    assert record.content_json["checks_total"] == 2
    assert record.tags and record.keywords_text


@pytest.mark.asyncio
async def test_specification_turn_posted_projects_prior_discussions(harness):
    project = await _make_project(harness)
    spec = await _make_specification(harness, project.id)
    turn = await _make_specification_turn(harness, spec.id, turn_index=0)

    event = build_event(
        type=EventType.SPECIFICATION_TURN_POSTED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={
            "specification_id": spec.id,
            "turn_index": 0,
            "role_key": "pm",
            "agent_id": None,
            "kind": "analysis",
        },
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.category == "prior_discussions"
    assert record.source_specification_id == spec.id
    assert record.content_json["excerpt"] == turn.text
    assert "kind:analysis" in record.tags
    assert "role:pm" in record.tags


@pytest.mark.asyncio
async def test_oversized_specification_content_is_dropped_and_marked_truncated(harness):
    project = await _make_project(harness)
    spec = await _make_specification(harness, project.id)
    huge_item = "x" * 500  # bound_text caps each list item at 300 bytes but the list as a whole is large
    await _make_specification_version(
        harness,
        spec.id,
        version=1,
        goals=[huge_item] * 20,
        requirements=[huge_item] * 20,
        acceptance_criteria=[huge_item] * 20,
        problem_statement="y" * 3000,
    )

    event = build_event(
        type=EventType.SPECIFICATION_APPROVED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"specification_id": spec.id, "version": 1},
    )
    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is not None
    assert record.content_json.get("_truncated") is True


# --- Extractor safety ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_payload_missing_required_field_returns_none_and_does_not_insert(harness):
    project = await _make_project(harness)
    event = Event(project_id=project.id, kind="system", type=EventType.TASK_FAILED, actor=SYSTEM_ACTOR, payload={})

    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is None
    assert await _all_memory_rows(harness) == []


@pytest.mark.asyncio
async def test_null_field_where_string_expected_does_not_raise(harness):
    project = await _make_project(harness)
    event = Event(
        project_id=project.id,
        kind="system",
        type=EventType.APPROVAL_GRANTED,
        actor=SYSTEM_ACTOR,
        payload={"approval_id": None},
    )

    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is None


@pytest.mark.asyncio
async def test_reference_to_nonexistent_row_returns_none(harness):
    project = await _make_project(harness)
    event = build_event(
        type=EventType.APPROVAL_GRANTED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"approval_id": "does-not-exist"}
    )

    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is None
    assert await _all_memory_rows(harness) == []


@pytest.mark.asyncio
async def test_unprojected_event_type_returns_none_immediately(harness):
    project = await _make_project(harness)
    event = build_event(
        type=EventType.TASK_CREATED,
        project_id=project.id,
        actor=SYSTEM_ACTOR,
        payload={"task_id": "t1", "title": "Whatever"},
    )

    record = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert record is None


# --- Deduplication --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_memory_called_twice_for_same_event_writes_one_row(harness):
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)
    approval = await _make_approval(harness, project.id, task.id)
    event = build_event(
        type=EventType.APPROVAL_GRANTED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"approval_id": approval.id}
    )

    first = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)
    second = await memory_service.record_memory(harness.session_factory, harness.event_bus, event)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    rows = await _all_memory_rows(harness)
    assert len(rows) == 1


# --- Subscriber isolation --------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_projects_a_real_event_published_through_the_bus(harness):
    install_memory_subscribers(harness.event_bus, harness.session_factory)
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)
    approval = await _make_approval(harness, project.id, task.id)

    await harness.event_bus.publish(
        build_event(type=EventType.APPROVAL_GRANTED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"approval_id": approval.id})
    )

    rows = await _all_memory_rows(harness)
    assert len(rows) == 1
    assert rows[0].category == "ceo_approvals"

    events = await harness.event_bus.recent(project.id, limit=10)
    memory_recorded = [e for e in events if e.type == "memory.recorded"]
    assert len(memory_recorded) == 1
    assert memory_recorded[0].payload["category"] == "ceo_approvals"


@pytest.mark.asyncio
async def test_subscribing_to_the_same_event_twice_writes_exactly_one_record(harness):
    install_memory_subscribers(harness.event_bus, harness.session_factory)
    install_memory_subscribers(harness.event_bus, harness.session_factory)
    project = await _make_project(harness)
    task = await _make_task(harness, project.id)
    approval = await _make_approval(harness, project.id, task.id)

    await harness.event_bus.publish(
        build_event(type=EventType.APPROVAL_GRANTED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"approval_id": approval.id})
    )

    rows = await _all_memory_rows(harness)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_a_raising_projection_extractor_does_not_break_publish(harness, monkeypatch):
    async def _boom(event, session):
        raise RuntimeError("extractor exploded")

    monkeypatch.setattr(memory_service, "EXTRACTORS", {EventType.TASK_COMPLETED: _boom})
    install_memory_subscribers(harness.event_bus, harness.session_factory)

    received: list[Event] = []

    async def other_subscriber(event: Event) -> None:
        received.append(event)

    harness.event_bus.subscribe(EventType.TASK_COMPLETED, other_subscriber)

    project = await _make_project(harness)
    task = await _make_task(harness, project.id)

    published = await harness.event_bus.publish(
        build_event(type=EventType.TASK_COMPLETED, project_id=project.id, actor=SYSTEM_ACTOR, payload={"task_id": task.id})
    )

    assert published is not None
    assert len(received) == 1
    assert await _all_memory_rows(harness) == []
