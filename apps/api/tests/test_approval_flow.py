from __future__ import annotations

import asyncio

import pytest

from app.core.lifecycle.task_states import TaskState
from app.modules.approvals import service as approvals_service
from app.modules.projects import service as projects_service
from app.modules.tasks import service as tasks_service


async def _wait_for_state(harness, task_id: str, *states: TaskState, timeout: float = 30.0) -> TaskState:
    """The workflow pipeline runs as a detached asyncio task with small
    pacing sleeps (see workflow_engine.CommanderWorkflowEngine), so tests
    poll for the resulting state rather than awaiting a return value."""
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} never reached {target}")


@pytest.mark.asyncio
async def test_approving_a_mission_completes_it(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Add search bar", "basic search", "normal"
    )

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )

    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    assert len(approvals) == 1

    decided = await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "approve", "Looks good"
    )
    assert decided.status == "approved"

    final_state = await _wait_for_state(harness, task.id, TaskState.COMPLETED)
    assert final_state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_rejecting_a_mission_cancels_it(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Delete prod DB", "bad idea", "high"
    )

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    decided = await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "reject", "Too risky"
    )
    assert decided.status == "rejected"

    final_state = await _wait_for_state(harness, task.id, TaskState.CANCELLED)
    assert final_state == TaskState.CANCELLED


@pytest.mark.asyncio
async def test_requesting_changes_sends_the_mission_back_for_rework(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Build login page", "email/password", "normal"
    )

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "request_changes", "Add validation"
    )

    reworked = await tasks_service.get_task(harness.session_factory, task.id)
    assert reworked.attempt == 2

    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL, TaskState.COMPLETED)
    assert final_state in (TaskState.PENDING_APPROVAL, TaskState.COMPLETED)
