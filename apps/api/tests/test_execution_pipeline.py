"""Sprint 6 Phase 2: the sandboxed-checks pipeline step (between the
Engineer's commit and the Reviewer's turn).

Drives `_land_code_changes` / `_run_checks` directly (same convention as
test_code_missions.py's diff-truncation test) since the mock provider's
fixed index.html/style.css output never contains a `.py`/`.test.js` file,
so no check would ever be detected through the full pipeline naturally.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.core.db_models import AgentORM
from app.core.lifecycle.task_states import TaskState
from app.modules.projects import service as projects_service
from app.modules.sandbox.settings import get_execution_enabled, set_execution_enabled
from app.modules.tasks import service as tasks_service

_PYTEST_DELIVERABLE = (
    "**Change Summary:** Added add() with a test.\n\n"
    "===== FILE: add.py =====\ndef add(a, b):\n    return a + b\n===== END FILE =====\n\n"
    "===== FILE: test_add.py =====\n"
    "from add import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    "===== END FILE ====="
)

_NO_MATCH_DELIVERABLE = (
    "**Change Summary:** Added the README.\n\n"
    "===== FILE: README.md =====\n# Hello\n===== END FILE ====="
)


async def _wait_for_state(harness, task_id: str, *states: TaskState, timeout: float = 30.0) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} never reached {target}")


async def _make_code_task(harness, title: str = "Add a function", description: str = "with a test"):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, title, description, "normal",
        deliverable_type="code",
    )
    async with harness.session_factory() as session:
        engineer_agent = (
            await session.execute(
                select(AgentORM).where(AgentORM.project_id == project.id, AgentORM.role == "engineer")
            )
        ).scalar_one()
    return project, task, engineer_agent


async def _land_and_run_checks(harness, task, engineer_agent, deliverable: str):
    await harness.workflow_engine._land_code_changes(task, engineer_agent, deliverable)
    branch_name = task.branch_name or harness.workflow_engine._branch_name_for(task.id)
    return await harness.workflow_engine._run_checks(task, branch_name)


@pytest.mark.asyncio
async def test_run_checks_detects_and_runs_matched_checks(harness):
    project, task, engineer_agent = await _make_code_task(harness)
    harness.sandbox_runner.default_status = "passed"

    summary, results = await _land_and_run_checks(harness, task, engineer_agent, _PYTEST_DELIVERABLE)

    assert results is not None
    names = {r["name"] for r in results}
    assert names == {"python-syntax", "pytest"}
    assert all(r["status"] == "passed" for r in results)
    assert "2/2 passed" in summary

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "execution.started" in types
    assert "execution.completed" in types


@pytest.mark.asyncio
async def test_run_checks_reports_could_not_run_when_sandbox_unavailable(harness):
    project, task, engineer_agent = await _make_code_task(harness)
    harness.sandbox_runner.available = False
    harness.sandbox_runner.unavailable_reason = "Docker Desktop is not running"

    summary, results = await _land_and_run_checks(harness, task, engineer_agent, _PYTEST_DELIVERABLE)

    assert results is not None
    assert all(r["status"] == "could_not_run" for r in results)
    assert "0/2 passed" in summary
    assert "Docker Desktop is not running" in summary

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "execution.completed" in types  # sandbox trouble is an event, never a pipeline crash


@pytest.mark.asyncio
async def test_run_checks_surfaces_failures_in_reviewer_summary(harness):
    from app.core.interfaces.sandbox import CheckResult

    project, task, engineer_agent = await _make_code_task(harness)
    harness.sandbox_runner._results["pytest"] = CheckResult(
        name="pytest", status="failed", duration_seconds=0.5, output="1 failed, 0 passed"
    )

    summary, results = await _land_and_run_checks(harness, task, engineer_agent, _PYTEST_DELIVERABLE)

    assert results is not None
    result_by_name = {r["name"]: r for r in results}
    assert result_by_name["pytest"]["status"] == "failed"
    assert "1/2 passed" in summary
    assert "pytest (failed)" in summary
    assert "1 failed, 0 passed" in summary


@pytest.mark.asyncio
async def test_run_checks_skips_when_no_checks_match(harness):
    project, task, engineer_agent = await _make_code_task(harness, title="Write the README")

    summary, results = await _land_and_run_checks(harness, task, engineer_agent, _NO_MATCH_DELIVERABLE)

    assert results is None
    assert summary == ""
    assert harness.sandbox_runner.calls == []


@pytest.mark.asyncio
async def test_run_checks_skips_when_execution_disabled(harness):
    project, task, engineer_agent = await _make_code_task(harness)
    await set_execution_enabled(harness.session_factory, project.id, False)
    assert await get_execution_enabled(harness.session_factory, project.id) is False

    summary, results = await _land_and_run_checks(harness, task, engineer_agent, _PYTEST_DELIVERABLE)

    assert results is None
    assert summary == ""
    assert harness.sandbox_runner.calls == []


@pytest.mark.asyncio
async def test_execution_enabled_defaults_true_when_never_set(harness):
    project, _task, _engineer = await _make_code_task(harness)

    assert await get_execution_enabled(harness.session_factory, project.id) is True


@pytest.mark.asyncio
async def test_full_pipeline_persists_check_results_on_the_task(harness):
    """End-to-end through `assign_task` -> `_run_pipeline`: the mock
    Engineer's deterministic output has no matching files, so this mainly
    guards that wiring `_run_checks` into `_run_pipeline` doesn't disturb
    the ordinary code-mission flow (item 2.8)."""
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Build landing page", "hero + tagline", "normal",
        deliverable_type="code",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    pending = await tasks_service.get_task(harness.session_factory, task.id)
    assert pending.check_results is None

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "execution.started" not in types
    assert "execution.completed" not in types
