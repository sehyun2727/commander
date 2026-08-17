"""Sprint 12 Phase 3: the Project Specification HTTP surface
(`app/modules/planning/routes.py`). `test_planning_orchestrator.py` already
covers the turn-loop's decision logic against the mock provider directly;
these tests cover what only exists at the route layer -- account scoping
(Rule #15), request validation, and CommanderError/InvalidTransition ->
HTTP status mapping (§4.10), plus the §4.7 approval gate end to end.
"""

from __future__ import annotations

import pytest

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
    resp = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "cto", "name": name}
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_start_planning_blocked_without_a_cto(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_start_planning_succeeds_once_a_cto_is_hired(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    resp = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready_for_review"
    assert body["current_version"] == 1

    listing = await api_client.get(f"/api/projects/{project_id}/specifications")
    assert listing.status_code == 200
    assert body["id"] in {s["id"] for s in listing.json()}

    versions = await api_client.get(f"/api/specifications/{body['id']}/versions")
    assert versions.status_code == 200
    assert len(versions.json()) == 1

    turns = await api_client.get(f"/api/specifications/{body['id']}/turns")
    assert turns.status_code == 200
    assert len(turns.json()) == 3


@pytest.mark.asyncio
async def test_second_concurrent_start_returns_409(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    first = await api_client.post(
        f"/api/projects/{project_id}/specifications",
        json={"request_text": f"{NEEDS_CLARIFICATION_MARKER}: build a thing"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "clarification_required"

    second = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "another request"}
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_clarification_answer_via_api(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications",
        json={"request_text": f"{NEEDS_CLARIFICATION_MARKER}: build a thing"},
    )
    spec_id = start.json()["id"]
    assert start.json()["status"] == "clarification_required"

    resumed = await api_client.post(
        f"/api/specifications/{spec_id}/clarification-answer",
        json={"answers": ["Success means it deploys cleanly."]},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "ready_for_review"


@pytest.mark.asyncio
async def test_revision_via_api_produces_a_second_version(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]

    revised = await api_client.post(
        f"/api/specifications/{spec_id}/revision", json={"feedback": "Please add rate limiting too"}
    )
    assert revised.status_code == 200
    assert revised.json()["current_version"] == 2

    versions = await api_client.get(f"/api/specifications/{spec_id}/versions")
    assert len(versions.json()) == 2


@pytest.mark.asyncio
async def test_reject_then_cancel_are_terminal_via_api(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]

    rejected = await api_client.post(
        f"/api/specifications/{spec_id}/reject", json={"reason": "Not aligned with the roadmap"}
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    again = await api_client.post(f"/api/specifications/{spec_id}/reject", json={})
    assert again.status_code == 409

    second_start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check, take two"}
    )
    assert second_start.status_code == 200


@pytest.mark.asyncio
async def test_approve_is_idempotent_guarded_by_409(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]

    approved = await api_client.post(f"/api/specifications/{spec_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    again = await api_client.post(f"/api/specifications/{spec_id}/approve")
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_begin_execution_requires_approval(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]

    resp = await api_client.post(f"/api/specifications/{spec_id}/begin-execution")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_begin_execution_after_approval_creates_and_assigns_a_mission(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]
    spec_title = (await api_client.get(f"/api/specifications/{spec_id}/versions")).json()[0]["title"]

    await api_client.post(f"/api/specifications/{spec_id}/approve")

    resp = await api_client.post(f"/api/specifications/{spec_id}/begin-execution")
    assert resp.status_code == 200
    task = resp.json()
    assert task["specification_id"] == spec_id
    assert task["state"] == "assigned"
    assert task["title"] == spec_title
    assert task["project_id"] == project_id

    tasks = await api_client.get(f"/api/projects/{project_id}/tasks")
    assert any(t["id"] == task["id"] for t in tasks.json())

    duplicate = await api_client.post(f"/api/specifications/{spec_id}/begin-execution")
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_cross_account_access_returns_404_not_403(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    await _hire_cto(api_client, project_id)
    start = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    spec_id = start.json()["id"]

    other_login = await api_client.post(
        "/api/auth/register",
        json={"email": "other-ceo@test.local", "password": "testpassword123", "display_name": "Other CEO"},
    )
    assert other_login.status_code == 200

    resp = await api_client.get(f"/api/specifications/{spec_id}")
    assert resp.status_code == 404

    resp = await api_client.get(f"/api/projects/{project_id}/specifications")
    assert resp.status_code == 404

    resp = await api_client.post(f"/api/specifications/{spec_id}/approve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_mock_e2e_flow_from_request_to_completed_mission(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    blocked = await api_client.post(
        f"/api/projects/{project_id}/specifications", json={"request_text": "Add a health check"}
    )
    assert blocked.status_code == 409

    await _hire_cto(api_client, project_id)

    start = await api_client.post(
        f"/api/projects/{project_id}/specifications",
        json={"request_text": f"{NEEDS_CLARIFICATION_MARKER}: Add a health check endpoint"},
    )
    assert start.status_code == 200
    spec_id = start.json()["id"]
    assert start.json()["status"] == "clarification_required"

    resumed = await api_client.post(
        f"/api/specifications/{spec_id}/clarification-answer",
        json={"answers": ["Success means the endpoint returns 200 when the app is healthy."]},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "ready_for_review"

    revised = await api_client.post(
        f"/api/specifications/{spec_id}/revision", json={"feedback": "Also log the check result"}
    )
    assert revised.status_code == 200
    assert revised.json()["current_version"] == 2

    approved = await api_client.post(f"/api/specifications/{spec_id}/approve")
    assert approved.status_code == 200

    started = await api_client.post(f"/api/specifications/{spec_id}/begin-execution")
    assert started.status_code == 200
    task_id = started.json()["id"]

    import asyncio

    for _ in range(50):
        task = await api_client.get(f"/api/tasks/{task_id}")
        if task.json()["state"] in {"completed", "in_review", "blocked", "failed"}:
            break
        await asyncio.sleep(0.1)
    assert task.json()["state"] in {"completed", "in_review", "blocked"}
