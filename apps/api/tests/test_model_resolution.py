from __future__ import annotations

import pytest

from app.modules.model_registry.service import set_role_model
from app.modules.projects.service import create_project
from app.modules.provider_gateway import build_gateway


@pytest.mark.asyncio
async def test_agent_override_wins_over_ceo_role_override_and_registry_default(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "anthropic"
    , owner_id=harness.user.id)
    await set_role_model(
        harness.session_factory,
        harness.event_bus,
        "anthropic",
        project.id,
        "builder",
        "claude-haiku-4-5-20251001",
    )
    gateway = build_gateway(
        "anthropic",
        harness.secrets,
        event_bus=harness.event_bus,
        project_id=project.id,
        session_factory=harness.session_factory,
    )
    # CEO set the role default to haiku, but this Employee has their own
    # agent-level override — that should win outright.
    resolved = await gateway.resolve_model("builder-default", agent_override="claude-sonnet-4-6")
    assert resolved == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_ceo_role_override_wins_when_no_agent_override(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "anthropic"
    , owner_id=harness.user.id)
    await set_role_model(
        harness.session_factory,
        harness.event_bus,
        "anthropic",
        project.id,
        "builder",
        "claude-haiku-4-5-20251001",
    )
    gateway = build_gateway(
        "anthropic",
        harness.secrets,
        event_bus=harness.event_bus,
        project_id=project.id,
        session_factory=harness.session_factory,
    )
    resolved = await gateway.resolve_model("builder-default", agent_override=None)
    assert resolved == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_registry_default_when_no_overrides_at_either_tier(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "anthropic"
    , owner_id=harness.user.id)
    gateway = build_gateway(
        "anthropic",
        harness.secrets,
        event_bus=harness.event_bus,
        project_id=project.id,
        session_factory=harness.session_factory,
    )
    resolved = await gateway.resolve_model("reviewer-default", agent_override=None)
    assert resolved == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_agent_override_wins_even_without_project_context(harness):
    gateway = build_gateway("mock", secrets=None)
    resolved = await gateway.resolve_model("planner-default", agent_override="mock-builder-v1")
    assert resolved == "mock-builder-v1"
