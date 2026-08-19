"""Sprint 17 §4.10/§8 (DECISIONS.md #239): `_fail_task_with_reason_code`
carries a structured `reason_code` on `TASK_FAILED`, additively, for the
two new mission-failure paths (`SelfCorrectionExhaustedError`,
`EmployeeSurrenderedError`). §4.15 records the decision to cover the
loop-level behavior behind these paths via orchestrator-level
`FakeGateway` tests (test_agent_harness_orchestrator.py) rather than a
full scripted pipeline run -- this file instead verifies the engine's own
reason-code plumbing directly, since that plumbing has no other coverage.
"""

from __future__ import annotations

import pytest

from app.core.db_models import TaskORM
from app.core.lifecycle.task_states import TaskState
from app.modules.projects import service as projects_service
from app.modules.tasks import service as tasks_service


async def _set_task_state(harness, task_id: str, state: TaskState) -> None:
    async with harness.session_factory() as session:
        row = await session.get(TaskORM, task_id)
        row.state = state.value
        await session.commit()


@pytest.mark.asyncio
async def test_fail_task_with_reason_code_transitions_and_carries_payload(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Mission", "", "normal", deliverable_type="code"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)

    await harness.workflow_engine._fail_task_with_reason_code(
        task.id, "self_correction_exhausted", "3 correction attempt(s) exhausted"
    )

    failed = await tasks_service.get_task(harness.session_factory, task.id)
    assert failed.state == TaskState.FAILED.value

    events = await harness.event_bus.recent(project.id, limit=50)
    failed_events = [e for e in events if e.type == "task.failed"]
    assert len(failed_events) == 1
    assert failed_events[0].payload["reason_code"] == "self_correction_exhausted"
    assert failed_events[0].payload["task_id"] == task.id
    assert failed_events[0].reason == "3 correction attempt(s) exhausted"


@pytest.mark.asyncio
async def test_fail_task_with_reason_code_supports_employee_surrendered(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Mission", "", "normal", deliverable_type="code"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)

    await harness.workflow_engine._fail_task_with_reason_code(
        task.id, "employee_surrendered", "**Unable to Complete:** the environment lacks a compiler"
    )

    failed = await tasks_service.get_task(harness.session_factory, task.id)
    assert failed.state == TaskState.FAILED.value

    events = await harness.event_bus.recent(project.id, limit=50)
    failed_events = [e for e in events if e.type == "task.failed"]
    assert len(failed_events) == 1
    assert failed_events[0].payload["reason_code"] == "employee_surrendered"
