"""Sprint 5, Phase 3: code missions end-to-end through the pipeline.

Uses the mock provider's deterministic 2-file (index.html/style.css)
code output (see mock_provider._code_deliverable_text) so these tests
never depend on network access or a real API key.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.lifecycle.task_states import TaskState
from app.modules.approvals import service as approvals_service
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
async def test_approving_a_code_mission_merges_and_records_stats(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
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

    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    pending = await tasks_service.get_task(harness.session_factory, task.id)
    assert pending.branch_name is not None
    assert pending.code_stats is not None
    assert pending.code_stats["files_added"] == 2
    assert "diff_text" not in pending.code_stats

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    assert len(approvals) == 1
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "approve", "Ship it"
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.COMPLETED)
    assert final_state == TaskState.COMPLETED

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "code.changed" in types
    assert "branch.merged" in types
    assert "workspace.initialized" in types

    merges = await harness.workspace_manager.recent_merges(project.id)
    assert any(m.subject == f"Merge {pending.branch_name}" for m in merges)


@pytest.mark.asyncio
async def test_rejecting_a_code_mission_leaves_the_branch_unmerged(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Build risky page",
        "not sure about this one",
        "normal",
        deliverable_type="code",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "reject", "Not needed"
    )
    final_state = await _wait_for_state(harness, task.id, TaskState.CANCELLED)
    assert final_state == TaskState.CANCELLED

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "code.changed" in types
    assert "branch.merged" not in types

    merges = await harness.workspace_manager.recent_merges(project.id)
    assert merges == []


@pytest.mark.asyncio
async def test_requesting_changes_recommits_to_the_same_branch(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Build a form",
        "needs validation",
        "normal",
        deliverable_type="code",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    first = await tasks_service.get_task(harness.session_factory, task.id)
    first_branch, first_sha = first.branch_name, first.code_stats["commit_sha"]

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "request_changes", "Add validation"
    )

    reworked = await tasks_service.get_task(harness.session_factory, task.id)
    assert reworked.attempt == 2

    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL, TaskState.COMPLETED)
    second = await tasks_service.get_task(harness.session_factory, task.id)
    assert second.branch_name == first_branch
    assert second.code_stats["commit_sha"] != first_sha


@pytest.mark.asyncio
async def test_document_mission_is_unaffected_by_workspace_wiring(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
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
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    pending = await tasks_service.get_task(harness.session_factory, task.id)
    assert pending.branch_name is None
    assert pending.code_stats is None
    assert pending.result_markdown

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "approve", "Nice"
    )
    final_state = await _wait_for_state(harness, task.id, TaskState.COMPLETED)
    assert final_state == TaskState.COMPLETED

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "code.changed" not in types
    assert "branch.merged" not in types
    assert "workspace.initialized" not in types


@pytest.mark.asyncio
async def test_merge_conflict_blocks_the_mission(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    task = await tasks_service.create_task(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "Build conflicting page",
        "will collide with main",
        "normal",
        deliverable_type="code",
    )
    await tasks_service.assign_task(
        harness.session_factory, harness.event_bus, harness.agent_runtime, harness.workflow_engine, task.id, None
    )
    await _wait_for_state(harness, task.id, TaskState.PENDING_APPROVAL)

    pending = await tasks_service.get_task(harness.session_factory, task.id)
    assert pending.branch_name is not None

    # Diverge main from the mission branch on the same path so the merge conflicts.
    await harness.workspace_manager.write_files(project.id, "main", {"index.html": "manually edited on main"})
    await harness.workspace_manager.commit(project.id, "main", "manual conflicting change")

    approvals = await approvals_service.list_pending(harness.session_factory, project.id)
    await approvals_service.decide(
        harness.session_factory, harness.workflow_engine, approvals[0].id, "approve", "Ship it"
    )

    final_state = await _wait_for_state(harness, task.id, TaskState.BLOCKED)
    assert final_state == TaskState.BLOCKED

    events = await harness.event_bus.recent(project.id, limit=200)
    types = [e.type for e in events]
    assert "branch.merged" not in types
    assert "task.state_changed" in types

    approval = await approvals_service.list_all(harness.session_factory, project.id)
    assert approval[0].status == "approved"
