"""Phase 2 pipeline data-ification tests (Sprint 9): verify
CommanderWorkflowEngine iterates `TEMPLATE.pipeline` generically -- an
arbitrary stage count, a repeated stage `kind`, and stage-index-based
resume -- using a test-only 4-stage pipeline built from the real
template's three roles. `software_company`'s real pipeline stays 3 stages
this sprint (docs/prompts/sprint-9.md §2.8); this file is the only place a
longer sequence exists.
"""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from app.core.db_models import TaskORM
from app.core.events.types import EventType
from app.core.lifecycle.task_states import TaskState
from app.modules.projects import service as projects_service
from app.modules.tasks import service as tasks_service
from app.modules.workflow_engine import engine as engine_module
from app.templates import TEMPLATE as REAL_TEMPLATE
from app.templates.software_company import StageSpec

# Four stages built from the real template's three roles, with "produce"
# appearing twice -- proving the engine tracks pipeline position by index,
# not by kind or role identity (Sprint 9, Rule #16).
_FOUR_STAGE_PIPELINE: tuple[StageSpec, ...] = (
    StageSpec(role_key="pm", kind="plan", lands_code=False, runs_checks=False),
    StageSpec(role_key="engineer", kind="produce", lands_code=False, runs_checks=False),
    StageSpec(role_key="engineer", kind="produce", lands_code=False, runs_checks=False),
    StageSpec(role_key="reviewer", kind="review", lands_code=False, runs_checks=False),
)

_TEST_TEMPLATE = dataclasses.replace(REAL_TEMPLATE, pipeline=_FOUR_STAGE_PIPELINE)


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


@pytest.mark.asyncio
async def test_engine_iterates_arbitrary_stage_count(harness, monkeypatch):
    monkeypatch.setattr(engine_module, "TEMPLATE", _TEST_TEMPLATE)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Four-stage mission", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)
    assert final_state == TaskState.PENDING_APPROVAL


@pytest.mark.asyncio
async def test_engine_supports_repeated_stage_kind(harness, monkeypatch):
    """Two `produce` stages in a row must each publish their own
    CodingStarted beat -- the engine dispatches per stage index, not once
    per distinct kind."""
    monkeypatch.setattr(engine_module, "TEMPLATE", _TEST_TEMPLATE)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Repeated produce", "", "normal"
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    items, _ = await harness.event_bus.page(project.id, None, 100, None)
    coding_started = [e for e in items if e.type == EventType.CODING_STARTED and e.payload["task_id"] == task.id]
    assert len(coding_started) == 2


@pytest.mark.asyncio
async def test_resume_from_nonzero_index_does_not_replay_in_progress_transition(harness, monkeypatch):
    """`resume_from=0` marks the mission `in_progress`; resuming from a
    later stage index (as a rework retry would) must not re-fire that
    transition -- IN_PROGRESS -> IN_PROGRESS isn't even a legal edge, so if
    the `resume_from == 0` guard ever regressed, this mission would fail
    instead of reaching PENDING_APPROVAL."""
    monkeypatch.setattr(engine_module, "TEMPLATE", _TEST_TEMPLATE)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Resume mid-pipeline", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)

    harness.workflow_engine._spawn(task.id, resume_from=3)  # index 3 == the review stage

    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)
    assert final_state == TaskState.PENDING_APPROVAL

    items, _ = await harness.event_bus.page(project.id, None, 100, None)
    task_started = [e for e in items if e.type == EventType.TASK_STARTED and e.payload["task_id"] == task.id]
    coding_started = [e for e in items if e.type == EventType.CODING_STARTED and e.payload["task_id"] == task.id]
    assert task_started == []
    assert coding_started == []


@pytest.mark.asyncio
async def test_resume_from_stage_index_skips_earlier_stages_entirely(harness, monkeypatch):
    """Resuming from index 2 (the second `produce` stage) must run only
    that stage plus the trailing review -- never the plan stage or the
    first produce stage -- proving `resume_from` is positional (a stage
    index), not looked up by role_key or kind."""
    monkeypatch.setattr(engine_module, "TEMPLATE", _TEST_TEMPLATE)
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Resume from index 2", "", "normal"
    )
    await _set_task_state(harness, task.id, TaskState.IN_PROGRESS)

    harness.workflow_engine._spawn(task.id, resume_from=2)

    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)
    assert final_state == TaskState.PENDING_APPROVAL

    items, _ = await harness.event_bus.page(project.id, None, 100, None)
    coding_started = [e for e in items if e.type == EventType.CODING_STARTED and e.payload["task_id"] == task.id]
    review_started = [e for e in items if e.type == EventType.REVIEW_STARTED and e.payload["task_id"] == task.id]
    assert len(coding_started) == 1
    assert len(review_started) == 1


@pytest.mark.asyncio
async def test_real_template_pipeline_is_still_three_stages():
    """Guardrail (Sprint 9 §2.8): the shipped `software_company` template's
    pipeline must not have grown this sprint -- this sprint builds the data
    structure, it does not add a fourth real stage. That is Sprint 10/11's
    job."""
    assert len(REAL_TEMPLATE.pipeline) == 3
    assert [stage.kind for stage in REAL_TEMPLATE.pipeline] == ["plan", "produce", "review"]
