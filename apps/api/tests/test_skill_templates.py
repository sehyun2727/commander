"""Sprint 11 Phase 1 §6.3: canonical, typed, immutable skill-template
registry, and the read-only API that exposes it."""

from __future__ import annotations

import dataclasses

import pytest

from app.modules.skill_templates.registry import (
    DEFAULT_SKILL_TEMPLATE_KEY,
    SKILL_TEMPLATES,
    SKILL_TEMPLATES_BY_KEY,
    GENERALIST,
)


def test_skill_template_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        GENERALIST.title = "Something Else"  # type: ignore[misc]


def test_skill_templates_registry_is_the_only_source():
    assert set(SKILL_TEMPLATES_BY_KEY.keys()) == {t.key for t in SKILL_TEMPLATES}
    assert len(SKILL_TEMPLATES) >= 1
    assert DEFAULT_SKILL_TEMPLATE_KEY in SKILL_TEMPLATES_BY_KEY


@pytest.mark.asyncio
async def test_skill_templates_api_exposes_only_safe_fields(api_client, harness):
    login = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login.status_code == 200
    project = await api_client.post("/api/projects", json={"name": "Skills Co", "provider": "mock"})
    assert project.status_code == 200

    resp = await api_client.get(f"/api/projects/{project.json()['id']}/skill-templates")
    assert resp.status_code == 200
    templates = resp.json()

    assert {t["key"] for t in templates} == {t.key for t in SKILL_TEMPLATES}
    for template in templates:
        assert set(template.keys()) == {"key", "title", "description"}


@pytest.mark.asyncio
async def test_skill_templates_api_cross_account_returns_404(api_client, harness):
    login = await api_client.post(
        "/api/auth/login", json={"email": harness.user.email, "password": "testpassword123"}
    )
    assert login.status_code == 200
    project = await api_client.post("/api/projects", json={"name": "Skills Co 2", "provider": "mock"})
    assert project.status_code == 200
    project_id = project.json()["id"]

    other = await api_client.post(
        "/api/auth/register",
        json={"email": "other-skills-ceo@test.local", "password": "otherpassword1", "display_name": "Other CEO"},
    )
    assert other.status_code == 200

    resp = await api_client.get(f"/api/projects/{project_id}/skill-templates")
    assert resp.status_code == 404
