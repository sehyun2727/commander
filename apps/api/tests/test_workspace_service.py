"""Sprint 5, Phase 4: read-only workspace service functions backing the
dashboard's /workspace page and per-mission diff view."""

from __future__ import annotations

import pytest

from app.modules.projects import service as projects_service
from app.modules.tasks import service as tasks_service
from app.modules.workspace_manager import service as workspace_service


async def _wait_for_pending_approval(harness, task_id: str, timeout: float = 30.0):
    import asyncio

    from app.core.lifecycle.task_states import TaskState

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(harness.session_factory, task_id)
        if task.state == TaskState.PENDING_APPROVAL.value:
            return task
        await asyncio.sleep(0.1)
    raise AssertionError(f"task {task_id} never reached PENDING_APPROVAL")


@pytest.mark.asyncio
async def test_project_exists(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    assert await workspace_service.project_exists(harness.session_factory, project.id) is True
    assert await workspace_service.project_exists(harness.session_factory, "no-such-project") is False


@pytest.mark.asyncio
async def test_get_tree_and_file_and_merges_after_a_code_mission(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Build landing page",
        "hero + tagline",
        "normal",
        deliverable_type="code",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    pending = await _wait_for_pending_approval(harness, task.id)

    diff = await tasks_service.get_diff(harness.session_factory, harness.workspace_manager, task.id)
    assert diff is not None
    diff_text, truncated = diff
    assert truncated is False
    assert diff_text

    from app.modules.approvals import service as approvals_service

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "approve", "Ship it"
    )

    tree = await workspace_service.get_tree(harness.session_factory, harness.workspace_manager, project.id, "main")
    paths = {entry.path for entry in tree}
    assert "index.html" in paths
    assert "style.css" in paths

    content = await workspace_service.get_file(
        harness.session_factory, harness.workspace_manager, project.id, "index.html", "main"
    )
    assert content is not None

    missing = await workspace_service.get_file(
        harness.session_factory, harness.workspace_manager, project.id, "no-such-file.txt", "main"
    )
    assert missing is None

    merges = await workspace_service.get_merges(harness.session_factory, harness.workspace_manager, project.id, 10)
    assert any(m.subject == f"Merge {pending.branch_name}" for m in merges)


@pytest.mark.asyncio
async def test_get_diff_is_none_for_document_missions(harness):
    project = await projects_service.create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    , owner_id=harness.user.id)
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Write the README",
        "explain the project",
        "normal",
        deliverable_type="document",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_pending_approval(harness, task.id)

    diff = await tasks_service.get_diff(harness.session_factory, harness.workspace_manager, task.id)
    assert diff is None
