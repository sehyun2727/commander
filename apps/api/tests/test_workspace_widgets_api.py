"""Sprint 15 Phase 2 §12: the CEO Workspace widget preference HTTP surface
(`app/modules/workspace_widgets/routes.py`) exercised end to end over real
HTTP -- ownership (Rule #15: 404 not 403), auth (401 unauthenticated),
structured validation errors, optimistic-concurrency conflicts, and that a
widget-layout mutation never touches any business/domain state. The pure
registry/normalization/validation logic is already covered in isolation by
`test_workspace_widgets_registry.py` / `test_workspace_widgets_service.py`;
this file follows the same route-level split `test_workspace_overview_api.py`
already establishes for Sprint 13.
"""

from __future__ import annotations

import pytest

from app.modules.workspace_widgets.registry import WIDGETS, WIDGETS_BY_KEY


async def _login_and_create_project(api_client, harness, name: str = "Acme") -> str:
    login = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login.status_code == 200
    project = await api_client.post("/api/projects", json={"name": name, "provider": "mock"})
    assert project.status_code == 200
    return project.json()["id"]


def _full_entries(overrides: dict[str, dict] | None = None) -> list[dict]:
    overrides = overrides or {}
    entries = []
    for widget in sorted(WIDGETS, key=lambda w: w.default_order):
        entry = {
            "widget_key": widget.key,
            "visible": widget.default_visible,
            "order": widget.default_order,
            "span": widget.default_span,
        }
        entry.update(overrides.get(widget.key, {}))
        entries.append(entry)
    return entries


@pytest.mark.asyncio
async def test_widgets_endpoint_requires_login(api_client):
    resp = await api_client.get("/api/projects/nonexistent/workspace/widgets")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_preferences_endpoint_requires_login(api_client):
    resp = await api_client.get("/api/projects/nonexistent/workspace/preferences")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_widgets_unknown_company_returns_404(api_client, harness):
    await api_client.post("/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"})
    resp = await api_client.get("/api/projects/nonexistent/workspace/widgets")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preferences_cross_account_access_returns_404_not_403(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-widgets-ceo@test.local", "password": "testpassword123", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.get(f"/api/projects/{project_id}/workspace/preferences")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_widgets_catalog_matches_registry(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    resp = await api_client.get(f"/api/projects/{project_id}/workspace/widgets")
    assert resp.status_code == 200
    body = resp.json()
    assert {w["key"] for w in body} == set(WIDGETS_BY_KEY.keys())


@pytest.mark.asyncio
async def test_default_preferences_are_returned_on_first_read(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    resp = await api_client.get(f"/api/projects/{project_id}/workspace/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["revision"] == 1
    assert {e["widget_key"] for e in body["widgets"]} == set(WIDGETS_BY_KEY.keys())
    assert all(e["visible"] for e in body["widgets"])


@pytest.mark.asyncio
async def test_valid_update_persists_across_reload(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    initial = (await api_client.get(f"/api/projects/{project_id}/workspace/preferences")).json()

    entries = _full_entries({"current_focus": {"visible": False}})
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences",
        json={"expected_revision": initial["revision"], "widgets": entries},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["revision"] == initial["revision"] + 1
    assert next(e for e in updated["widgets"] if e["widget_key"] == "current_focus")["visible"] is False

    reread = (await api_client.get(f"/api/projects/{project_id}/workspace/preferences")).json()
    assert reread["revision"] == updated["revision"]
    assert next(e for e in reread["widgets"] if e["widget_key"] == "current_focus")["visible"] is False


@pytest.mark.asyncio
async def test_reset_restores_default_layout(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    initial = (await api_client.get(f"/api/projects/{project_id}/workspace/preferences")).json()
    await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences",
        json={"expected_revision": initial["revision"], "widgets": _full_entries({"current_focus": {"visible": False}})},
    )

    resp = await api_client.post(f"/api/projects/{project_id}/workspace/preferences/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert all(e["visible"] for e in body["widgets"])


@pytest.mark.asyncio
async def test_preferences_are_isolated_per_company(api_client, harness):
    project_a = await _login_and_create_project(api_client, harness, name="Acme A")
    initial = (await api_client.get(f"/api/projects/{project_a}/workspace/preferences")).json()
    await api_client.put(
        f"/api/projects/{project_a}/workspace/preferences",
        json={"expected_revision": initial["revision"], "widgets": _full_entries({"current_focus": {"visible": False}})},
    )

    project_b = await _login_and_create_project(api_client, harness, name="Acme B")
    b_prefs = (await api_client.get(f"/api/projects/{project_b}/workspace/preferences")).json()
    assert next(e for e in b_prefs["widgets"] if e["widget_key"] == "current_focus")["visible"] is True


@pytest.mark.asyncio
async def test_preferences_are_isolated_per_user(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    initial = (await api_client.get(f"/api/projects/{project_id}/workspace/preferences")).json()
    await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences",
        json={"expected_revision": initial["revision"], "widgets": _full_entries({"current_focus": {"visible": False}})},
    )

    other_email = "other-widgets-isolation@test.local"
    reg = await api_client.post(
        "/api/auth/register",
        json={"email": other_email, "password": "otherpassword1", "display_name": "Other CEO"},
    )
    assert reg.status_code == 200
    other_project = await api_client.post("/api/projects", json={"name": "Other Co", "provider": "mock"})
    other_project_id = other_project.json()["id"]

    resp = await api_client.get(f"/api/projects/{other_project_id}/workspace/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert next(e for e in body["widgets"] if e["widget_key"] == "current_focus")["visible"] is True


@pytest.mark.asyncio
async def test_update_rejects_unknown_widget_key(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    entries = _full_entries()[:-1]
    entries.append({"widget_key": "not_a_real_widget", "visible": True, "order": 99, "span": "half"})
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences", json={"expected_revision": 1, "widgets": entries}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_rejects_duplicate_widget_key(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    entries = _full_entries()
    entries[-1] = dict(entries[0])
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences", json={"expected_revision": 1, "widgets": entries}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_rejects_missing_widget(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    entries = _full_entries()[:-1]
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences", json={"expected_revision": 1, "widgets": entries}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_rejects_required_widget_hidden(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    entries = _full_entries({"connection_status": {"visible": False}})
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences", json={"expected_revision": 1, "widgets": entries}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_rejects_stale_revision(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    initial = (await api_client.get(f"/api/projects/{project_id}/workspace/preferences")).json()
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences",
        json={"expected_revision": initial["revision"] + 999, "widgets": _full_entries()},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"] == "stale_revision"
    assert body["detail"]["current_revision"] == initial["revision"]


@pytest.mark.asyncio
async def test_update_rejects_oversized_widget_payload(api_client, harness):
    project_id = await _login_and_create_project(api_client, harness)
    entries = _full_entries()
    entries.append({"widget_key": "extra_ninth_widget", "visible": True, "order": 99, "span": "half"})
    resp = await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences", json={"expected_revision": 1, "widgets": entries}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_never_mutates_any_business_state(api_client, harness):
    """§4.6: a widget-layout change is presentation-only -- it must never
    touch Task/Approval/Specification/Event rows or any other business
    truth. Confirmed here by checking the event stream is untouched."""
    project_id = await _login_and_create_project(api_client, harness)
    before = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    assert before.status_code == 200
    before_cursor = before.json()["event_cursor"]

    initial = (await api_client.get(f"/api/projects/{project_id}/workspace/preferences")).json()
    await api_client.put(
        f"/api/projects/{project_id}/workspace/preferences",
        json={"expected_revision": initial["revision"], "widgets": _full_entries({"current_focus": {"visible": False}})},
    )
    await api_client.post(f"/api/projects/{project_id}/workspace/preferences/reset")

    after = await api_client.get(f"/api/projects/{project_id}/workspace/overview")
    assert after.json()["event_cursor"] == before_cursor
