"""Phase 1 reliability tests (Sprint 9): orphan mission recovery, mission
cancel, and the mission budget guard. See docs/prompts/sprint-9.md Phase 1
and CLAUDE.md Rule #13.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.db_models import AgentORM, TaskORM
from app.core.events.types import EventType
from app.core.lifecycle.agent_states import AgentState
from app.core.lifecycle.task_states import TaskState
from app.modules.projects import service as projects_service
from app.modules.tasks import service as tasks_service
from app.modules.tasks.service import recover_orphaned_tasks


async def _wait_for_state(harness, task_id: str, *states: TaskState, timeout: float = 30.0) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.05)
    raise AssertionError(f"task {task_id} never reached {target}")


async def _set_task_state(harness, task_id: str, state: TaskState) -> None:
    async with harness.session_factory() as session:
        row = await session.get(TaskORM, task_id)
        row.state = state.value
        await session.commit()


async def _set_agent_state(harness, agent_id: str, state: AgentState, current_task_id: str | None) -> None:
    async with harness.session_factory() as session:
        row = await session.get(AgentORM, agent_id)
        row.state = state.value
        row.current_task_id = current_task_id
        await session.commit()


async def _engineer_agent_id(harness, project_id: str) -> str:
    async with harness.session_factory() as session:
        result = await session.execute(
            select(AgentORM).where(AgentORM.project_id == project_id, AgentORM.role_key == "engineer")
        )
        return result.scalars().one().id


async def _wait_for_event(harness, project_id: str, event_type: EventType, timeout: float = 5.0):
    """The BUDGET_EXCEEDED publish happens just after the task's BLOCKED
    commit, not before it -- polling on task state alone can win the race
    against the event actually landing, so tests that assert on the event
    itself poll for it directly."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        items, _ = await harness.event_bus.page(project_id, None, 50, None)
        matches = [e for e in items if e.type == event_type]
        if matches:
            return matches
        await asyncio.sleep(0.05)
    raise AssertionError(f"event {event_type} never appeared for project {project_id}")


# --- Orphan mission recovery -------------------------------------------------


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_blocks_in_progress_mission(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Orphaned mission", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)

    recovered_ids = await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    assert task.id in recovered_ids
    reloaded = await tasks_service.get_task(harness.session_factory, task.id)
    assert reloaded.state == TaskState.BLOCKED.value


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_blocks_in_review_mission(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Orphaned mission", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_REVIEW)

    recovered_ids = await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    assert task.id in recovered_ids
    reloaded = await tasks_service.get_task(harness.session_factory, task.id)
    assert reloaded.state == TaskState.BLOCKED.value


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_leaves_resting_states_untouched(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    pending = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Waiting on CEO", "", "normal"
    )
    await _set_task_state(harness, pending.id, TaskState.PENDING_APPROVAL)
    completed = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Already done", "", "normal"
    )
    await _set_task_state(harness, completed.id, TaskState.COMPLETED)

    recovered_ids = await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    assert pending.id not in recovered_ids
    assert completed.id not in recovered_ids
    assert (await tasks_service.get_task(harness.session_factory, pending.id)).state == TaskState.PENDING_APPROVAL.value
    assert (await tasks_service.get_task(harness.session_factory, completed.id)).state == TaskState.COMPLETED.value


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_emits_task_recovered_event(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Orphaned mission", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)

    await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    items, _ = await harness.event_bus.page(project.id, None, 50, None)
    recovered_events = [e for e in items if e.type == EventType.TASK_RECOVERED]
    assert any(e.payload["task_id"] == task.id for e in recovered_events)


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_frees_stuck_agent(harness):
    """Found during Sprint 9's own DoD verification (docs/DECISIONS.md):
    the Employee whose coroutine died with an orphaned Mission was left
    parked in AgentState.WORKING forever, so the next Mission ever
    assigned to that Employee crashed with InvalidTransition
    (WORKING -> ASSIGNED). Recovery must free the Employee, not just the
    Mission."""
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Orphaned mission", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)
    engineer_id = await _engineer_agent_id(harness, project.id)
    await _set_agent_state(harness, engineer_id, AgentState.WORKING, task.id)

    recovered_ids = await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    assert task.id in recovered_ids
    async with harness.session_factory() as session:
        agent_row = await session.get(AgentORM, engineer_id)
        assert agent_row.state == AgentState.IDLE.value
        assert agent_row.current_task_id is None


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_leaves_idle_agents_untouched(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Orphaned mission", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)
    engineer_id = await _engineer_agent_id(harness, project.id)

    await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    async with harness.session_factory() as session:
        agent_row = await session.get(AgentORM, engineer_id)
        assert agent_row.state == AgentState.IDLE.value


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_emits_agent_state_changed_event(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Orphaned mission", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)
    engineer_id = await _engineer_agent_id(harness, project.id)
    await _set_agent_state(harness, engineer_id, AgentState.WORKING, task.id)

    await recover_orphaned_tasks(harness.session_factory, harness.event_bus)

    items, _ = await harness.event_bus.page(project.id, None, 50, None)
    agent_events = [
        e for e in items if e.type == EventType.AGENT_STATE_CHANGED and e.payload["agent_id"] == engineer_id
    ]
    assert any(e.payload["new_state"] == AgentState.IDLE.value for e in agent_events)


# --- Mission cancel -----------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_running_mission_transitions_to_cancelled_and_frees_agent(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Cancel me", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.IN_PROGRESS, TaskState.IN_REVIEW)

    ok = await harness.workflow_engine.cancel_task(task.id, "CEO changed priorities")
    assert ok is True

    final_state = await _wait_for_state(harness, task.id, TaskState.CANCELLED)
    assert final_state == TaskState.CANCELLED

    engineer_id = await _engineer_agent_id(harness, project.id)
    deadline = asyncio.get_event_loop().time() + 5.0
    state = await harness.agent_runtime.get_state(engineer_id)
    while state != AgentState.IDLE and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.05)
        state = await harness.agent_runtime.get_state(engineer_id)
    assert state == AgentState.IDLE

    # Sprint 10 §0.8: current_task_id must not still point at the
    # cancelled mission, or a CEO message sent right afterward would
    # route to a mission that no longer exists for this Employee.
    async with harness.session_factory() as session:
        agent_row = await session.get(AgentORM, engineer_id)
        assert agent_row.current_task_id is None


@pytest.mark.asyncio
async def test_cancel_completed_mission_is_rejected(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Already done", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.COMPLETED)

    ok = await harness.workflow_engine.cancel_task(task.id, "too late")
    assert ok is False
    reloaded = await tasks_service.get_task(harness.session_factory, task.id)
    assert reloaded.state == TaskState.COMPLETED.value


@pytest.mark.asyncio
async def test_cancel_missing_task_returns_false(harness):
    ok = await harness.workflow_engine.cancel_task("does-not-exist", "n/a")
    assert ok is False


@pytest.mark.asyncio
async def test_cancel_mission_with_no_running_coroutine_uses_fallback(harness):
    """A mission in `pending_approval` has no live asyncio.Task (the
    pipeline already finished) -- cancel must still work via the direct
    DB-transition fallback path in `CommanderWorkflowEngine.cancel_task`."""
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Waiting on CEO", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.PENDING_APPROVAL)

    ok = await harness.workflow_engine.cancel_task(task.id, "CEO abandoned this mission")
    assert ok is True
    reloaded = await tasks_service.get_task(harness.session_factory, task.id)
    assert reloaded.state == TaskState.CANCELLED.value


# --- Mission budget guard -----------------------------------------------------


@pytest.mark.asyncio
async def test_budget_exceeded_tokens_blocks_the_mission(harness, monkeypatch):
    monkeypatch.setattr(settings, "commander_mission_max_tokens", -1)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Too expensive", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.BLOCKED)
    assert final_state == TaskState.BLOCKED


@pytest.mark.asyncio
async def test_budget_exceeded_usd_blocks_the_mission(harness, monkeypatch):
    monkeypatch.setattr(settings, "commander_mission_max_usd", -1.0)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Too expensive", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.BLOCKED)
    assert final_state == TaskState.BLOCKED


@pytest.mark.asyncio
async def test_budget_exceeded_seconds_blocks_the_mission(harness, monkeypatch):
    monkeypatch.setattr(settings, "commander_mission_max_seconds", -1)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Too slow", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.BLOCKED)
    assert final_state == TaskState.BLOCKED


@pytest.mark.asyncio
async def test_budget_exceeded_emits_event_with_limit_details(harness, monkeypatch):
    monkeypatch.setattr(settings, "commander_mission_max_tokens", -1)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Too expensive", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.BLOCKED)

    budget_events = await _wait_for_event(harness, project.id, EventType.BUDGET_EXCEEDED)
    assert len(budget_events) == 1
    payload = budget_events[0].payload
    assert payload["task_id"] == task.id
    assert payload["limit_kind"] == "tokens"
    assert payload["stage"] == "pm"


@pytest.mark.asyncio
async def test_mission_completes_normally_when_under_budget(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Cheap mission", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)
    assert final_state == TaskState.PENDING_APPROVAL
