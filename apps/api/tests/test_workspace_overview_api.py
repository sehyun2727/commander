"""Sprint 13 Phase 2 §7/§9: the CEO Workspace snapshot HTTP surface
(`app/modules/workspace_overview/routes.py`). `test_workspace_next_action.py`
and `test_workspace_schemas.py` already cover the pure policy/schema layer
in isolation; these tests exercise the real route end to end -- ownership
(Rule #15: 404 not 403), and that `next_action`/`focus`/summaries actually
track real domain state across the founding -> planning -> approval ->
execution -> failure lifecycle, per §9's concurrency/consistency scenarios
and §12's "API/integration tests" list.
"""

from __future__ import annotations

import pytest

from app.core.db_models import ApprovalORM, TaskORM
from app.core.lifecycle.task_states import TaskState
from app.modules.provider_gateway.mock_provider import NEEDS_CLARIFICATION_MARKER
from app.modules.workspace_overview.schemas import MAX_RECENT_ACTIVITY, MAX_RECENT_MISSIONS


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


async def _create_task_directly(
    harness, project_id: str, state: TaskState, *, specification_id: str | None = None, title: str = "Add a health check"
) -> str:
    """Inserts a TaskORM row in a chosen state without ever going through
    `assign_task`/the live `WorkflowEngine` pipeline -- the pipeline is a
    real background asyncio task and racing a direct state write against it
    is inherently flaky (confirmed: both writers can legally observe the
    same `current` state and one loses to an `InvalidTransition`). This
    module is a read-only projection, so seeding the exact row state
    directly is the correct and deterministic way to test it, matching the
    existing `test_reports.py` precedent of writing ORM rows straight."""
    async with harness.session_factory() as session:
        task = TaskORM(
            project_id=project_id,
            title=title,
            description="d",
            priority="normal",
            state=state.value,
            specification_id=specification_id,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task.id


@pytest.mark.asyncio
async def test_overview_requires_login(api_client):
    resp = await api_client.get("/api/projects/nonexistent/workspace/overview")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_overview_unknown_company_returns_404(api_client, harness):
    await api_client.post("/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"})
    resp = await api_client.get("/api/projects/nonexistent/workspace/overview")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_overview_cross_account_access_returns_404_not_403(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-ceo@test.local", "password": "testpassword123", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_overview_fresh_company_surfaces_vacant_leadership_before_start_mission(api_client, harness):
    """A freshly founded Company has PM/Reviewer auto-seeded but CTO vacant
    (Sprint 11) -- tier 8 must fire before tier 9's has_any_task check."""
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 1
    assert body["next_action"]["kind"] == "setup_leadership"
    assert body["next_action"]["target_resource_id"] == "cto"
    assert body["focus"]["resource_type"] == "role"
    assert any(slot["role_key"] == "cto" and not slot["occupied"] for slot in body["organization"]["leadership"])


@pytest.mark.asyncio
async def test_overview_shows_start_mission_once_leadership_is_filled(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_action"]["kind"] == "start_mission"
    assert body["next_action"]["requires_ceo_input"] is True
    assert all(slot["occupied"] for slot in body["organization"]["leadership"])


@pytest.mark.asyncio
async def test_overview_reflects_clarification_required(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications",
        json={"request_text": f"{NEEDS_CLARIFICATION_MARKER}: build a thing"},
    )
    assert start.status_code == 200
    spec_id = start.json()["id"]

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert body["next_action"]["kind"] == "answer_clarification"
    assert body["next_action"]["target_resource_id"] == spec_id
    assert body["pending_actions"]["clarification"]["specification_id"] == spec_id
    assert body["planning"]["status"] == "clarification_required"


@pytest.mark.asyncio
async def test_overview_reflects_specification_ready_for_review(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert body["next_action"]["kind"] == "review_specification"
    assert body["pending_actions"]["specification_review"]["specification_id"] == spec_id
    assert body["planning"]["active"] is True


@pytest.mark.asyncio
async def test_overview_reflects_approved_specification_ready_to_execute(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]
    await api_client.post(f"/api/specifications/{spec_id}/approve")

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert body["next_action"]["kind"] == "begin_execution"
    assert body["planning"]["status"] == "approved"
    assert body["planning"]["active"] is False


@pytest.mark.asyncio
async def test_overview_reflects_active_mission_after_execution_begins(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]
    await api_client.post(f"/api/specifications/{spec_id}/approve")

    task_id = await _create_task_directly(harness, project_id, TaskState.IN_PROGRESS, specification_id=spec_id)

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert body["next_action"]["kind"] == "monitor_mission"
    assert body["next_action"]["target_resource_id"] == task_id
    assert body["next_action"]["requires_ceo_input"] is False
    assert any(m["id"] == task_id for m in body["missions"]["active"])
    # tier 6 must not re-fire once a Mission exists for the approved spec.
    assert body["next_action"]["kind"] != "begin_execution"


@pytest.mark.asyncio
async def test_overview_reflects_mission_failure(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]
    await api_client.post(f"/api/specifications/{spec_id}/approve")

    task_id = await _create_task_directly(harness, project_id, TaskState.FAILED, specification_id=spec_id)

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert body["next_action"]["kind"] == "resolve_mission_failure"
    assert body["next_action"]["target_resource_id"] == task_id
    assert body["pending_actions"]["failure"]["resource_type"] == "task"
    assert body["pending_actions"]["failure"]["resource_id"] == task_id


@pytest.mark.asyncio
async def test_overview_reflects_pending_approval(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]
    await api_client.post(f"/api/specifications/{spec_id}/approve")
    started = await api_client.post(f"/api/specifications/{spec_id}/begin-execution")
    task_id = started.json()["id"]

    async with harness.session_factory() as session:
        approval = ApprovalORM(project_id=project_id, task_id=task_id, subject="Ship the health check")
        session.add(approval)
        await session.commit()
        await session.refresh(approval)
        approval_id = approval.id

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert body["next_action"]["kind"] == "review_approval"
    assert body["next_action"]["target_resource_id"] == task_id
    assert body["pending_actions"]["approval"]["approval_id"] == approval_id
    assert body["focus"]["resource_type"] == "task" and body["focus"]["resource_id"] == task_id


@pytest.mark.asyncio
async def test_overview_bounds_recent_missions_and_activity(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    for i in range(MAX_RECENT_MISSIONS + 5):
        resp = await api_client.post(
            f"/api/projects/{project_id}/tasks", json={"title": f"Mission {i}", "description": "d", "priority": "normal"}
        )
        assert resp.status_code == 200

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    assert len(body["missions"]["recent"]) <= MAX_RECENT_MISSIONS
    assert len(body["recent_activity"]) <= MAX_RECENT_ACTIVITY


@pytest.mark.asyncio
async def test_overview_never_leaks_raw_event_payload(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()
    for item in body["recent_activity"]:
        assert "payload" not in item
        assert set(item.keys()) == {"id", "seq", "type", "kind", "actor_role", "actor_name", "reason", "created_at"}


@pytest.mark.asyncio
async def test_overview_service_issues_a_bounded_fixed_number_of_queries(api_client, harness):
    """§6/§12: the projection must be a small, fixed number of sequential
    selects (situation/reports precedent, DECISIONS.md #219) -- never one
    query per row (N+1). Bounded regardless of how much data exists."""
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)
    for i in range(5):
        resp = await api_client.post(
            f"/api/projects/{project_id}/tasks", json={"title": f"Mission {i}", "description": "d", "priority": "normal"}
        )
        assert resp.status_code == 200

    from sqlalchemy import event as sa_event

    from app.modules.workspace_overview.service import get_workspace_snapshot

    async with harness.session_factory() as probe_session:
        sync_engine = probe_session.bind.sync_engine

    statements: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa_event.listen(sync_engine, "before_cursor_execute", _count)
    try:
        snapshot = await get_workspace_snapshot(harness.session_factory, project_id)
    finally:
        sa_event.remove(sync_engine, "before_cursor_execute", _count)

    assert snapshot is not None
    select_statements = [s for s in statements if s.strip().upper().startswith("SELECT")]
    assert len(select_statements) <= 15, f"expected a small fixed query count, got {len(select_statements)}"


@pytest.mark.asyncio
async def test_overview_event_cursor_matches_max_seq_for_the_project(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    body = resp.json()

    from sqlalchemy import func, select

    from app.core.db_models import EventORM

    async with harness.session_factory() as session:
        max_seq = (
            await session.execute(select(func.max(EventORM.seq)).where(EventORM.project_id == project_id))
        ).scalar()

    assert body["event_cursor"] == max_seq
