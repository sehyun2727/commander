"""Sprint 13 Phase 3 §9/§12: event and lifecycle integration for the CEO
Workspace snapshot. `test_workspace_overview_api.py` already proves each
individual state produces the right snapshot in isolation; these tests
prove `next_action` actually *changes* correctly as a single Company moves
through real, API-driven domain transitions, and that terminal/cancelled/
rejected outcomes clear a stale next_action rather than leaving it stuck
(§9's consistency scenarios, §12's "next_action changes after authoritative
transitions" / "cancellation/failure removes stale actions" requirements).

No new event types were needed for this sprint: every specification/
approval/mission transition already publishes a distinct EventType
(see app/core/events/types.py) that `recent_activity` surfaces through
existing safe fields -- confirmed by reading the enum directly rather than
assuming a gap existed.
"""

from __future__ import annotations

import pytest

from app.core.db_models import ApprovalORM, TaskORM
from app.modules.approvals import service as approvals_service
from app.modules.provider_gateway.mock_provider import NEEDS_CLARIFICATION_MARKER


async def _login_and_create_project(api_client, harness, name: str = "Acme") -> str:
    login = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login.status_code == 200
    project = await api_client.post("/api/projects", json={"name": name, "provider": "mock"})
    assert project.status_code == 200
    return project.json()["id"]


async def _hire_cto(api_client, project_id: str, name: str = "Ada") -> None:
    resp = await api_client.post(f"/api/projects/{project_id}/agents", json={"role_key": "cto", "name": name})
    assert resp.status_code == 201


async def _next_action_kind(api_client, project_id: str) -> str:
    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    assert resp.status_code == 200
    return resp.json()["next_action"]["kind"]


@pytest.mark.asyncio
async def test_next_action_tracks_the_full_founding_to_execution_lifecycle(api_client, harness):
    """§12: run an API-level mock lifecycle and capture the next_action at
    every stage -- setup_leadership -> start_mission -> answer_clarification
    -> review_specification -> begin_execution -> (an active-or-terminal
    Mission state, never stuck on begin_execution again)."""
    project_id = await _login_and_create_project(api_client, harness)

    assert await _next_action_kind(api_client, project_id) == "setup_leadership"

    await _hire_cto(api_client, project_id)
    assert await _next_action_kind(api_client, project_id) == "start_mission"

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications",
        json={"request_text": f"{NEEDS_CLARIFICATION_MARKER}: build a thing"},
    )
    spec_id = start.json()["id"]
    assert await _next_action_kind(api_client, project_id) == "answer_clarification"

    await api_client.post(
        f"/api/specifications/{spec_id}/clarification-answer",
        json={"answers": ["Success means it deploys cleanly."]},
    )
    assert await _next_action_kind(api_client, project_id) == "review_specification"

    await api_client.post(f"/api/specifications/{spec_id}/approve")
    assert await _next_action_kind(api_client, project_id) == "begin_execution"

    await api_client.post(f"/api/specifications/{spec_id}/begin-execution")
    # tier 6 (begin_execution) must never re-fire once a Mission exists for
    # this specification -- whatever the live mock pipeline does next is an
    # active-monitoring or terminal/attention outcome, never "start over".
    assert await _next_action_kind(api_client, project_id) != "begin_execution"


@pytest.mark.asyncio
async def test_next_action_clears_once_a_ready_for_review_specification_is_rejected(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]
    assert await _next_action_kind(api_client, project_id) == "review_specification"

    rejected = await api_client.post(f"/api/specifications/{spec_id}/reject", json={"reason": "Out of scope"})
    assert rejected.status_code == 200

    # REJECTED is terminal and outside every next_action predicate -- a
    # rejected Specification must not keep surfacing a stale review action.
    kind = await _next_action_kind(api_client, project_id)
    assert kind != "review_specification"
    assert kind == "start_mission"


@pytest.mark.asyncio
async def test_next_action_clears_once_planning_is_cancelled(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications",
        json={"request_text": f"{NEEDS_CLARIFICATION_MARKER}: build a thing"},
    )
    spec_id = start.json()["id"]
    assert await _next_action_kind(api_client, project_id) == "answer_clarification"

    cancelled = await api_client.post(f"/api/specifications/{spec_id}/cancel", json={"reason": "No longer needed"})
    assert cancelled.status_code == 200

    kind = await _next_action_kind(api_client, project_id)
    assert kind != "answer_clarification"
    assert kind == "start_mission"


@pytest.mark.asyncio
async def test_next_action_clears_pending_approval_once_decided(api_client, harness):
    """A code Mission with no branch_name skips the merge-to-main step inside
    `_approve_task` (workflow_engine/engine.py), so `decide()` can drive this
    task straight from PENDING_APPROVAL to COMPLETED -- a legal transition
    per TASK_TRANSITIONS -- without needing a real Git workspace/branch."""
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    async with harness.session_factory() as session:
        task = TaskORM(project_id=project_id, title="Ship it", description="d", priority="normal", state="pending_approval")
        session.add(task)
        await session.commit()
        await session.refresh(task)
        approval = ApprovalORM(project_id=project_id, task_id=task.id, subject="Ship it")
        session.add(approval)
        await session.commit()
        await session.refresh(approval)
        approval_id = approval.id

    assert await _next_action_kind(api_client, project_id) == "review_approval"

    # decide() delegates the actual status mutation to
    # workflow_engine.resume_after_decision -- decision is "approve", not
    # "approved" (see workflow_engine/engine.py resume_after_decision).
    await approvals_service.decide(harness.session_factory, harness.workflow_engine, approval_id, "approve", None)

    kind = await _next_action_kind(api_client, project_id)
    assert kind != "review_approval"
