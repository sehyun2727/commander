"""Sprint 19 §7.2: `_spawn` sets `task_id_var` around the whole background
pipeline; `_run_role` / `_run_engineer_tool_loop` additionally set
`agent_id_var` / `project_id_var` around their own execution. These tests
spy on the call each method makes into provider/tool-loop code -- the
point where a real log call would happen inside those bodies -- and check
the ambient contextvars against the real ids passed as arguments, rather
than duplicating a full mission run's worth of assertions."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

import app.modules.workflow_engine.engine as engine_module
from app.core.lifecycle.task_states import TaskState
from app.core.logging import JSONFormatter, agent_id_var, project_id_var, task_id_var
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


@pytest.mark.asyncio
async def test_document_mission_propagates_contextvars_into_stream_say(harness, monkeypatch):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Write the README",
        "explain the project",
        "normal",
        deliverable_type="document",
    )

    captured: list[dict] = []
    original = harness.workflow_engine._stream_say

    async def spy(project_id, agent, task_id, gateway, model_ref, **opts):
        captured.append(
            {
                "arg_project_id": project_id,
                "arg_agent_id": agent.id,
                "arg_task_id": task_id,
                "var_project_id": project_id_var.get(),
                "var_agent_id": agent_id_var.get(),
                "var_task_id": task_id_var.get(),
            }
        )
        return await original(project_id, agent, task_id, gateway, model_ref, **opts)

    monkeypatch.setattr(harness.workflow_engine, "_stream_say", spy)

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    # A document mission runs multiple stages (plan/produce/review), each
    # calling `_stream_say` once via its own `_run_role` -- every one of
    # those calls must see its own stage's agent/project id ambient.
    assert len(captured) >= 1
    for snapshot in captured:
        assert snapshot["var_task_id"] == snapshot["arg_task_id"] == task.id
        assert snapshot["var_agent_id"] == snapshot["arg_agent_id"]
        assert snapshot["var_project_id"] == snapshot["arg_project_id"] == project.id


@pytest.mark.asyncio
async def test_code_mission_propagates_contextvars_into_tool_loop(harness, monkeypatch):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Build landing page",
        "hero + tagline",
        "normal",
        deliverable_type="code",
    )

    captured: list[dict] = []
    original = engine_module.run_tool_loop

    async def spy(*, context, **kwargs):
        captured.append(
            {
                "arg_project_id": context.project_id,
                "arg_agent_id": context.agent_id,
                "arg_task_id": context.task_id,
                "var_project_id": project_id_var.get(),
                "var_agent_id": agent_id_var.get(),
                "var_task_id": task_id_var.get(),
            }
        )
        return await original(context=context, **kwargs)

    monkeypatch.setattr(engine_module, "run_tool_loop", spy)

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    assert len(captured) == 1
    snapshot = captured[0]
    assert snapshot["var_task_id"] == snapshot["arg_task_id"] == task.id
    assert snapshot["var_agent_id"] == snapshot["arg_agent_id"]
    assert snapshot["var_project_id"] == snapshot["arg_project_id"] == project.id


@pytest.mark.asyncio
async def test_cancelled_pipeline_log_carries_task_id_but_not_agent_or_project_id(harness):
    """`_run_pipeline`'s `except asyncio.CancelledError` log fires after
    `_run_role`'s own `except asyncio.CancelledError` handler has already
    released the agent and its `finally` has reset `agent_id_var`/
    `project_id_var` -- only `task_id_var` (set by `_spawn`, still in
    scope for the whole pipeline) should be ambient by the time that log
    call happens."""
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )
    task = await tasks_service.create_task(
        harness.session_factory, harness.event_bus, project.id, "Cancel me", "", "normal"
    )

    # Format inside `emit()` itself, not afterward -- `JSONFormatter` reads
    # contextvars live at format() time, and by the time this test's own
    # coroutine resumes after `_wait_for_state`, it's back in the test's
    # context (never inside the pipeline's), not the background task's.
    formatter = JSONFormatter()
    payloads: list[dict] = []

    class _CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            payloads.append(json.loads(formatter.format(record)))

    handler = _CapturingHandler()
    target_logger = logging.getLogger("commander.workflow_engine")
    target_logger.addHandler(handler)
    # Tests never call `install_logging()` (root stays at the logging
    # module's default WARNING level), so INFO-level calls would otherwise
    # be filtered before reaching this handler.
    saved_level = target_logger.level
    target_logger.setLevel(logging.INFO)
    try:
        await tasks_service.assign_task(
            harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
        )
        await _wait_for_state(harness, task.id, TaskState.IN_PROGRESS, TaskState.IN_REVIEW)

        ok = await harness.workflow_engine.cancel_task(task.id, "test cancel")
        assert ok is True
        await _wait_for_state(harness, task.id, TaskState.CANCELLED)
    finally:
        target_logger.removeHandler(handler)
        target_logger.setLevel(saved_level)

    cancelled_payloads = [p for p in payloads if "cancelled" in p["msg"]]
    assert len(cancelled_payloads) == 1
    assert cancelled_payloads[0]["task_id"] == task.id
    assert "agent_id" not in cancelled_payloads[0]
    assert "project_id" not in cancelled_payloads[0]
