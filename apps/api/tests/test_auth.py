from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.db_models import SessionORM
from app.modules.auth import service as auth_service

pytestmark = pytest.mark.asyncio


async def test_register_creates_account_and_logs_in(api_client):
    resp = await api_client.post(
        "/api/auth/register",
        json={"email": "new-ceo@test.local", "password": "supersecret1", "display_name": "New CEO"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "new-ceo@test.local"
    assert "commander_session" in resp.cookies


async def test_register_duplicate_email_rejected(api_client):
    body = {"email": "dupe@test.local", "password": "supersecret1", "display_name": "Dupe"}
    first = await api_client.post("/api/auth/register", json=body)
    assert first.status_code == 200

    second = await api_client.post("/api/auth/register", json=body)
    assert second.status_code == 409


async def test_login_wrong_password_and_unknown_email_share_one_message(api_client, harness):
    wrong_password = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "not-the-password"}
    )
    unknown_email = await api_client.post(
        "/api/auth/login", json={"email": "nobody@test.local", "password": "whatever123"}
    )
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


async def test_login_success_sets_session_cookie(api_client, harness):
    resp = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert resp.status_code == 200
    assert "commander_session" in resp.cookies


async def test_me_without_cookie_returns_401(api_client):
    resp = await api_client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_with_valid_cookie_returns_current_user(api_client, harness):
    await api_client.post("/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"})
    resp = await api_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == harness.user.id


async def test_logout_revokes_session(api_client, harness):
    await api_client.post("/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"})
    logout_resp = await api_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    me_resp = await api_client.get("/api/auth/me")
    assert me_resp.status_code == 401


async def test_expired_session_returns_401(api_client, harness):
    login_resp = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login_resp.status_code == 200

    token_hash = auth_service._hash_token(login_resp.cookies["commander_session"])
    async with harness.session_factory() as session:
        row = await session.get(SessionORM, token_hash)
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()

    resp = await api_client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_unauthenticated_project_list_returns_401(api_client):
    resp = await api_client.get("/api/projects")
    assert resp.status_code == 401


async def test_cross_account_project_access_returns_404(api_client, harness):
    project = await _create_project(api_client, harness, "Owner's Company")

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-ceo@test.local", "password": "otherpassword1", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 404


async def test_own_project_is_accessible(api_client, harness):
    project = await _create_project(api_client, harness, "My Company")
    resp = await api_client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


async def test_cross_account_task_access_returns_404(api_client, harness):
    project = await _create_project(api_client, harness, "Task Owner Co")
    task_resp = await api_client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Ship it", "description": "desc", "priority": "normal"},
    )
    assert task_resp.status_code == 200
    task_id = task_resp.json()["id"]

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-task-ceo@test.local", "password": "otherpassword1", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 404


async def test_sse_stream_requires_auth(api_client):
    resp = await api_client.get("/api/events/stream", params={"project_id": "no-such-project"})
    assert resp.status_code == 401


async def test_sse_stream_cross_account_returns_404(api_client, harness):
    project = await _create_project(api_client, harness, "Stream Owner Co")

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-sse-ceo@test.local", "password": "otherpassword1", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.get("/api/events/stream", params={"project_id": project["id"]})
    assert resp.status_code == 404


async def _create_project(api_client, harness, name: str) -> dict:
    login = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login.status_code == 200
    resp = await api_client.post("/api/projects", json={"name": name, "provider": "mock"})
    assert resp.status_code == 200
    return resp.json()
