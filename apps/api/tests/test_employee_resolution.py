"""Sprint 10 Phase 3: the Role -> Employee resolver.

`resolve_employee_for_role` is a pure function (§12/§13), so most cases
here construct `AgentORM` instances directly rather than going through the
DB -- only the event-emission test needs a real pipeline run.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.db_models import AgentORM
from app.core.lifecycle.agent_states import AgentState
from app.core.lifecycle.task_states import TaskState
from app.modules.agent_runtime.service import create_employee
from app.modules.projects.service import create_project
from app.modules.tasks import service as tasks_service
from app.modules.workflow_engine.employee_resolution import resolve_employee_for_role


def _agent(
    agent_id: str,
    *,
    state: str = AgentState.IDLE.value,
    created_at: datetime | None = None,
    last_assigned_at: datetime | None = None,
) -> AgentORM:
    return AgentORM(
        id=agent_id,
        project_id="p1",
        role_key="engineer",
        name=agent_id,
        profile={},
        avatar_color="#000000",
        state=state,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_assigned_at=last_assigned_at,
    )


def test_prefers_an_idle_employee_over_a_busy_one():
    busy = _agent("busy", state=AgentState.WORKING.value)
    idle = _agent("idle", state=AgentState.IDLE.value)

    selected, rule = resolve_employee_for_role([busy, idle])

    assert selected.id == "idle"
    assert rule == "idle"


def test_among_idle_candidates_picks_the_one_waiting_longest():
    recently_assigned = _agent("recent", last_assigned_at=datetime(2026, 1, 5, tzinfo=timezone.utc))
    never_assigned = _agent("never", last_assigned_at=None)
    assigned_a_while_ago = _agent("a_while_ago", last_assigned_at=datetime(2026, 1, 2, tzinfo=timezone.utc))

    selected, rule = resolve_employee_for_role([recently_assigned, never_assigned, assigned_a_while_ago])

    assert selected.id == "never"  # "never assigned" waits longer than any real timestamp
    assert rule == "idle"


def test_no_idle_employee_falls_back_to_the_whole_role():
    busy_longer_wait = _agent(
        "busy_longer_wait", state=AgentState.WORKING.value, last_assigned_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    busy_shorter_wait = _agent(
        "busy_shorter_wait", state=AgentState.BLOCKED.value, last_assigned_at=datetime(2026, 1, 5, tzinfo=timezone.utc)
    )

    selected, rule = resolve_employee_for_role([busy_shorter_wait, busy_longer_wait])

    assert selected.id == "busy_longer_wait"
    assert rule == "no_idle_fallback"


def test_ties_break_by_created_at_then_stable_id():
    same_instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _agent("a", last_assigned_at=None, created_at=same_instant)
    b = _agent("b", last_assigned_at=None, created_at=same_instant)

    selected, _ = resolve_employee_for_role([b, a])

    assert selected.id == "a"


def test_selection_is_deterministic_regardless_of_input_order():
    candidates = [
        _agent("x", last_assigned_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
        _agent("y", last_assigned_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _agent("z", last_assigned_at=None),
    ]

    forward, _ = resolve_employee_for_role(candidates)
    reversed_, _ = resolve_employee_for_role(list(reversed(candidates)))

    assert forward.id == reversed_.id == "z"


def test_resolve_employee_for_role_rejects_an_empty_pool():
    with pytest.raises(ValueError):
        resolve_employee_for_role([])


async def _wait_for_state(harness, task_id: str, *states: TaskState, timeout: float = 30.0) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} never reached {target}")


@pytest.mark.asyncio
async def test_pipeline_run_emits_agent_resolved_for_every_stage(harness):
    """Sprint 10 §14: every stage's Employee selection is Event-observable,
    with a second Engineer present so the resolver has an actual choice to
    make for the "produce" stage, not just a pool of one."""
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )
    async with harness.session_factory() as session:
        founding_engineer = (
            await session.execute(
                select(AgentORM).where(AgentORM.project_id == project.id, AgentORM.role_key == "engineer")
            )
        ).scalar_one()
    await create_employee(harness.session_factory, project.id, "engineer")

    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Build landing page", "hero + tagline", "normal",
        deliverable_type="code",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    events = await harness.event_bus.recent(project.id, limit=200)
    resolved = [e for e in events if e.type == "agent.resolved"]

    resolved_role_keys = {e.payload["role_key"] for e in resolved}
    assert resolved_role_keys == {"pm", "engineer", "reviewer"}
    for event in resolved:
        assert event.payload["rule"] in ("idle", "no_idle_fallback")
        assert event.payload["agent_id"]

    # Both Engineers are idle and never assigned at pipeline start -- the
    # deterministic created_at tie-break must land on the founding one.
    engineer_resolution = next(e for e in resolved if e.payload["role_key"] == "engineer")
    assert engineer_resolution.payload["agent_id"] == founding_engineer.id
    assert engineer_resolution.payload["rule"] == "idle"
