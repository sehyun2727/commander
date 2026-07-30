from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.contracts import DecisionStyle, Personality
from app.core.db_models import AgentORM
from app.core.events.types import EventType
from app.modules.agent_profiles import service as agent_profiles
from app.modules.agent_profiles.service import InvalidModelRefError
from app.modules.projects.service import create_project


async def _pm_agent_id(harness, project_id: str) -> str:
    async with harness.session_factory() as session:
        result = await session.execute(
            select(AgentORM).where(AgentORM.project_id == project_id, AgentORM.role == "pm")
        )
        return result.scalar_one().id


@pytest.mark.asyncio
async def test_get_profile_returns_founding_default(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)
    agent_id = await _pm_agent_id(harness, project.id)

    profile = await agent_profiles.get_profile(harness.session_factory, agent_id)
    assert profile.personality == Personality.PROFESSIONAL
    assert profile.custom_instructions == ""
    assert profile.model_ref is None


@pytest.mark.asyncio
async def test_update_profile_persists_and_emits_event_with_changed_fields(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)
    agent_id = await _pm_agent_id(harness, project.id)

    updated = await agent_profiles.update_profile(
        harness.session_factory,
        harness.event_bus,
        agent_id,
        {"personality": Personality.DIRECT, "custom_instructions": "Be terse."},
    )
    assert updated.personality == Personality.DIRECT
    assert updated.custom_instructions == "Be terse."
    # Unset fields keep their prior values, not schema defaults.
    assert updated.decision_style == DecisionStyle.BALANCED

    reread = await agent_profiles.get_profile(harness.session_factory, agent_id)
    assert reread == updated

    events = await harness.event_bus.recent(project.id)
    profile_events = [e for e in events if e.type == EventType.AGENT_PROFILE_UPDATED]
    assert len(profile_events) == 1
    assert profile_events[0].payload["agent_id"] == agent_id
    assert set(profile_events[0].payload["changed_fields"]) == {"personality", "custom_instructions"}
    assert "Priya Shah" in profile_events[0].reason


@pytest.mark.asyncio
async def test_update_profile_with_no_actual_change_emits_no_event(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)
    agent_id = await _pm_agent_id(harness, project.id)

    await agent_profiles.update_profile(
        harness.session_factory, harness.event_bus, agent_id, {"personality": Personality.PROFESSIONAL}
    )

    events = await harness.event_bus.recent(project.id)
    assert not [e for e in events if e.type == EventType.AGENT_PROFILE_UPDATED]


@pytest.mark.asyncio
async def test_update_profile_unknown_agent_raises(harness):
    with pytest.raises(ValueError):
        await agent_profiles.update_profile(
            harness.session_factory, harness.event_bus, "nonexistent-id", {"personality": Personality.DIRECT}
        )


@pytest.mark.asyncio
async def test_get_profile_unknown_agent_raises(harness):
    with pytest.raises(ValueError):
        await agent_profiles.get_profile(harness.session_factory, "nonexistent-id")


@pytest.mark.asyncio
async def test_update_profile_accepts_a_known_model_ref_for_the_role(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)
    agent_id = await _pm_agent_id(harness, project.id)

    updated = await agent_profiles.update_profile(
        harness.session_factory, harness.event_bus, agent_id, {"model_ref": "mock-planner-v1"}
    )
    assert updated.model_ref == "mock-planner-v1"


@pytest.mark.asyncio
async def test_update_profile_rejects_a_model_ref_not_valid_for_the_role(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)
    agent_id = await _pm_agent_id(harness, project.id)

    with pytest.raises(InvalidModelRefError):
        await agent_profiles.update_profile(
            harness.session_factory, harness.event_bus, agent_id, {"model_ref": "mock-reviewer-v1"}
        )


@pytest.mark.asyncio
async def test_update_profile_rejects_a_completely_unknown_model_ref(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)
    agent_id = await _pm_agent_id(harness, project.id)

    with pytest.raises(InvalidModelRefError):
        await agent_profiles.update_profile(
            harness.session_factory, harness.event_bus, agent_id, {"model_ref": "not-a-real-model"}
        )
