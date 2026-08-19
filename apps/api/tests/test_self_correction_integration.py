"""End-to-end pipeline coverage for Sprint 17 self-correction scenarios
(DECISIONS.md #239).

Drives `mock_provider.py`'s `SELF_CORRECTION_DEMO`/`SELF_CORRECTION_ROLLBACK`
scripted scenarios through the real pipeline (assign -> Engineer tool loop
-> Reviewer -> PENDING_APPROVAL), with zero provider keys. A `run_validation`
call always returns the same canned `CheckResult` for a given profile name
in the stock `FakeSandbox`, which can't express "fails once, then passes" --
so these tests monkeypatch `harness.sandbox_runner.run_check` with a small
per-call sequenced replacement (test-only; the real `SandboxRunner`
interface and `TEMPLATE.checks` are untouched), per Sprint 17 §4.15.

`SELF_CORRECTION_EXHAUSTED`/`SELF_CORRECTION_SURRENDER` are deliberately not
scripted as full-pipeline scenarios here -- §4.15 explicitly allows covering
those paths via orchestrator-level `FakeGateway` tests instead
(test_agent_harness_orchestrator.py already does), since a full pipeline
run would add no coverage beyond what those loop-mechanics tests already
exercise directly. This test file instead covers the `_fail_task_with_reason_code`
mapping those paths rely on (see `test_workflow_engine_reason_code.py`).
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.core.db_models import HarnessToolCallORM
from app.core.interfaces.sandbox import CheckResult
from app.core.lifecycle.task_states import TaskState
from app.modules.projects import service as projects_service
from app.modules.tasks import service as tasks_service


async def _wait_for_state(harness, task_id: str, *states: TaskState, timeout: float = 30.0) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} never reached {target}")


def _sequence_validation_statuses(harness, statuses: list[str]) -> None:
    """Sprint 17 §4.15: a test-only per-call sequenced replacement for
    `FakeSandbox.run_check` -- the stock `FakeSandbox` keys canned results
    by profile name, which can't express the same profile failing once and
    then passing later in the same mission."""
    remaining = list(statuses)

    async def run_check(name: str, files: dict[str, str], command: list[str]) -> CheckResult:
        status = remaining.pop(0) if remaining else "passed"
        harness.sandbox_runner.calls.append((name, files, command))
        return CheckResult(
            name=name, status=status, duration_seconds=0.01, output="ok" if status == "passed" else "check failed"
        )

    harness.sandbox_runner.run_check = run_check


@pytest.mark.asyncio
async def test_self_correction_demo_scenario_completes_without_intercepting(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    _sequence_validation_statuses(harness, ["failed", "passed"])
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "SELF_CORRECTION_DEMO landing page",
        "demonstrate self-correction",
        "normal",
        deliverable_type="code",
    )

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL, TaskState.FAILED)

    assert final_state == TaskState.PENDING_APPROVAL

    events = await harness.event_bus.recent(project.id, limit=200)
    assert not any(e.type == "agent.self_correction_triggered" for e in events)

    summary = await tasks_service.get_harness_summary(harness.session_factory, task.id)
    assert summary is not None
    assert summary["correction_attempts"] == 0
    assert summary["surrendered"] is False
    assert summary["exhausted"] is False
    assert summary["rollback_count"] == 0
    assert "apply_patch" in summary["tools_used"]
    assert "run_validation" in summary["tools_used"]


@pytest.mark.asyncio
async def test_self_correction_rollback_scenario_reverts_then_lands_a_fix(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    _sequence_validation_statuses(harness, ["failed", "passed"])
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "SELF_CORRECTION_ROLLBACK landing page",
        "demonstrate rollback",
        "normal",
        deliverable_type="code",
    )

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    final_state = await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL, TaskState.FAILED)

    assert final_state == TaskState.PENDING_APPROVAL

    summary = await tasks_service.get_harness_summary(harness.session_factory, task.id)
    assert summary is not None
    assert summary["rollback_count"] == 1
    assert "revert_last_patch" in summary["tools_used"]

    async with harness.session_factory() as session:
        rows = (
            await session.execute(
                select(HarnessToolCallORM).where(
                    HarnessToolCallORM.task_id == task.id, HarnessToolCallORM.tool_name == "revert_last_patch"
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "success"
