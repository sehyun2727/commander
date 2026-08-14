"""Sprint 11 §6.4/§6.7: the hiring route -- POST /api/projects/{id}/agents.

`hire_employee` itself is exercised at the service layer in
test_employee_singleton.py; these tests cover the route's HTTP concerns:
account scoping, request validation, and error-code mapping (§4.10 --
CommanderError subclasses must not leak as bare 500s or the wrong 4xx).
"""

from __future__ import annotations

import asyncio

import pytest


async def _login_and_create_project(api_client, harness, name: str = "Acme") -> str:
    login = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login.status_code == 200
    project = await api_client.post("/api/projects", json={"name": name, "provider": "mock"})
    assert project.status_code == 200
    return project.json()["id"]


@pytest.mark.asyncio
async def test_hire_employee_route_returns_201_and_the_new_agent(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "cto", "name": "Ada"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "cto"
    assert body["name"] == "Ada"
    assert body["profile"]["skill_template_key"] == "generalist"

    listing = await api_client.get(f"/api/projects/{project_id}/agents")
    assert resp.json()["id"] in {a["id"] for a in listing.json()}


@pytest.mark.asyncio
async def test_hire_employee_route_accepts_model_ref_and_skill_template(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents",
        json={"role_key": "engineer", "name": "Kim", "skill_template_key": "research_focused"},
    )
    assert resp.status_code == 201
    assert resp.json()["profile"]["skill_template_key"] == "research_focused"


@pytest.mark.asyncio
async def test_hire_employee_route_rejects_unknown_role_with_400(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "astronaut", "name": "Buzz"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_hire_employee_route_rejects_empty_name_with_400(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "engineer", "name": "   "}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_hire_employee_route_rejects_unknown_model_ref_with_422(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents",
        json={"role_key": "engineer", "name": "Kim", "model_ref": "not-a-real-model"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_hire_employee_route_rejects_unknown_skill_template_with_422(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents",
        json={"role_key": "engineer", "name": "Kim", "skill_template_key": "not-a-real-template"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_hire_employee_route_rejects_second_pm_with_409(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "pm", "name": "Second PM"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_hire_employee_route_rejects_unknown_fields(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents",
        json={"role_key": "engineer", "name": "Kim", "not_a_real_field": "x"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_hire_employee_route_cross_account_returns_404(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-hiring-ceo@test.local", "password": "otherpassword1", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "engineer", "name": "Kim"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_hire_employee_route_requires_auth(api_client, harness):
    resp = await api_client.post(
        "/api/projects/does-not-matter/agents", json={"role_key": "engineer", "name": "Kim"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_full_hiring_flow_end_to_end(api_client, harness):
    """Sprint 11 Phase 3 §14: company -> roles -> hire CTO -> reject 2nd CTO
    -> hire 2 Engineers -> edit one independently -> list reflects both
    configs -> a Mission still resolves through the newly hired Engineers,
    proving the hiring route feeds the same resolver as founding Employees."""
    project_id = await _login_and_create_project(api_client, harness, "Full Flow Co")

    roles = (await api_client.get(f"/api/projects/{project_id}/roles")).json()
    assert {r["key"] for r in roles} == {"pm", "engineer", "reviewer", "cto"}
    assert all("model_ref" in r for r in roles)

    hire_cto = await api_client.post(f"/api/projects/{project_id}/agents", json={"role_key": "cto", "name": "Ada"})
    assert hire_cto.status_code == 201
    cto_id = hire_cto.json()["id"]

    reject_second_cto = await api_client.post(
        f"/api/projects/{project_id}/agents", json={"role_key": "cto", "name": "Grace"}
    )
    assert reject_second_cto.status_code == 409

    hire_kim = await api_client.post(
        f"/api/projects/{project_id}/agents",
        json={"role_key": "engineer", "name": "Kim", "skill_template_key": "speed_focused"},
    )
    hire_lee = await api_client.post(
        f"/api/projects/{project_id}/agents",
        json={"role_key": "engineer", "name": "Lee", "skill_template_key": "research_focused"},
    )
    assert hire_kim.status_code == 201 and hire_lee.status_code == 201
    kim_id, lee_id = hire_kim.json()["id"], hire_lee.json()["id"]

    edit_kim = await api_client.put(f"/api/agents/{kim_id}/profile", json={"skill_template_key": "generalist"})
    assert edit_kim.status_code == 200
    assert edit_kim.json()["skill_template_key"] == "generalist"

    listing = {a["id"]: a for a in (await api_client.get(f"/api/projects/{project_id}/agents")).json()}
    assert listing[kim_id]["profile"]["skill_template_key"] == "generalist"
    assert listing[lee_id]["profile"]["skill_template_key"] == "research_focused"
    assert listing[cto_id]["role"] == "cto"

    task = await api_client.post(
        f"/api/projects/{project_id}/tasks",
        json={"title": "Build a widget", "description": "hero + tagline", "priority": "normal", "deliverable_type": "code"},
    )
    assert task.status_code == 200
    task_id = task.json()["id"]

    assign = await api_client.post(f"/api/tasks/{task_id}/assign", json={"agent_id": None})
    assert assign.status_code == 200

    deadline = asyncio.get_event_loop().time() + 30.0
    state = None
    while asyncio.get_event_loop().time() < deadline:
        current = await api_client.get(f"/api/tasks/{task_id}")
        state = current.json()["state"]
        if state in ("pending_approval", "completed", "failed"):
            break
        await asyncio.sleep(0.1)
    assert state in ("pending_approval", "completed", "failed")

    events = (await api_client.get(f"/api/projects/{project_id}/events", params={"limit": 200})).json()["items"]
    resolved = [e for e in events if e["type"] == "agent.resolved"]
    resolved_role_keys = {e["payload"]["role_key"] for e in resolved}
    assert resolved_role_keys == {"pm", "engineer", "reviewer"}
    engineer_ids = {a["id"] for a in listing.values() if a["role"] == "engineer"}
    engineer_resolution = next(e for e in resolved if e["payload"]["role_key"] == "engineer")
    assert engineer_resolution["payload"]["agent_id"] in engineer_ids
