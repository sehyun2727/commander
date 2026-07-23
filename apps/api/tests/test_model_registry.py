from __future__ import annotations

import pytest

from app.core.events.types import EventType
from app.modules.model_registry import options_for_role
from app.modules.model_registry.overrides import get_override
from app.modules.model_registry.service import effective_model, list_catalog, set_role_model
from app.modules.projects.service import create_project
from app.modules.provider_gateway import build_gateway


def test_options_for_role_restricts_mock_to_its_own_model_per_role():
    # Mock's output is templated by substring-matching the model id, so
    # only its own recommended model is a safe choice per role.
    assert options_for_role("mock", "planner") == ["mock-planner-v1"]
    assert options_for_role("mock", "reviewer") == ["mock-reviewer-v1"]


def test_options_for_role_anthropic_allows_any_model_for_any_role():
    options = options_for_role("anthropic", "reviewer")
    assert "claude-haiku-4-5-20251001" in options
    assert "claude-sonnet-4-6" in options


@pytest.mark.asyncio
async def test_list_catalog_defaults_to_recommended_with_no_override(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")
    catalog = await list_catalog(harness.session_factory, "mock", project.id)
    by_role = {entry["role"]: entry for entry in catalog}
    assert by_role["builder"]["current_model"] == "mock-builder-v1"
    assert by_role["builder"]["recommended_model"] == "mock-builder-v1"
    assert by_role["builder"]["options"] == ["mock-builder-v1"]


@pytest.mark.asyncio
async def test_set_role_model_rejects_unavailable_model(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")
    with pytest.raises(ValueError):
        await set_role_model(
            harness.session_factory, harness.event_bus, "mock", project.id, "reviewer", "mock-planner-v1"
        )


@pytest.mark.asyncio
async def test_set_role_model_persists_override_and_emits_event(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "anthropic"
    )
    await set_role_model(
        harness.session_factory,
        harness.event_bus,
        "anthropic",
        project.id,
        "builder",
        "claude-haiku-4-5-20251001",
    )

    override = await get_override(harness.session_factory, project.id, "builder")
    assert override == "claude-haiku-4-5-20251001"

    model = await effective_model(harness.session_factory, "anthropic", project.id, "builder")
    assert model == "claude-haiku-4-5-20251001"

    events = await harness.event_bus.recent(project.id)
    changed = [e for e in events if e.type == EventType.MODEL_CHANGED]
    assert len(changed) == 1
    assert changed[0].payload == {
        "role": "builder",
        "previous_model": "claude-sonnet-4-6",
        "new_model": "claude-haiku-4-5-20251001",
    }
    assert changed[0].reason == "CEO reassigned Engineer to claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_set_role_model_to_same_value_does_not_emit_event(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "anthropic"
    )
    recommended = await effective_model(harness.session_factory, "anthropic", project.id, "builder")
    await set_role_model(harness.session_factory, harness.event_bus, "anthropic", project.id, "builder", recommended)

    events = await harness.event_bus.recent(project.id)
    assert not [e for e in events if e.type == EventType.MODEL_CHANGED]


@pytest.mark.asyncio
async def test_gateway_resolve_model_honors_override(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "anthropic"
    )
    await set_role_model(
        harness.session_factory,
        harness.event_bus,
        "anthropic",
        project.id,
        "planner",
        "claude-sonnet-4-6",
    )
    gateway = build_gateway(
        "anthropic",
        harness.secrets,
        event_bus=harness.event_bus,
        project_id=project.id,
        session_factory=harness.session_factory,
    )
    assert await gateway.resolve_model("planner-default") == "claude-sonnet-4-6"
    assert await gateway.resolve_model("builder-default") == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_gateway_resolve_model_falls_back_without_project_context():
    gateway = build_gateway("mock", secrets=None)
    assert await gateway.resolve_model("planner-default") == "mock-planner-v1"
