from __future__ import annotations

import asyncio

import pytest

from app.core.lifecycle.task_states import TaskState
from app.modules.projects import service as projects_service
from app.modules.situation import service as situation_service
from app.modules.tasks import service as tasks_service


async def _wait_for_state(harness, task_id: str, *states, timeout: float = 30.0):
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state in target:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} never reached {target}")


@pytest.mark.asyncio
async def test_situation_is_calm_for_a_freshly_founded_company(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    result = await situation_service.get_situation(harness.session_factory, harness.secrets, harness.event_bus, project.id)
    assert result is not None
    text, generated_at = result
    assert "quiet" in text.lower() or "no missions" in text.lower()
    assert generated_at is not None


@pytest.mark.asyncio
async def test_situation_mentions_pending_decisions_once_a_mission_reaches_review(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Ship it", "desc", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    text, _ = await situation_service.get_situation(
        harness.session_factory, harness.secrets, harness.event_bus, project.id
    )
    assert "1 decision" in text


@pytest.mark.asyncio
async def test_situation_for_unknown_project_returns_none(harness):
    result = await situation_service.get_situation(
        harness.session_factory, harness.secrets, harness.event_bus, "nonexistent-id"
    )
    assert result is None
