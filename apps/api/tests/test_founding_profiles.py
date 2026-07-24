from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.contracts import AgentProfile, DecisionStyle, Personality, WorkingStyle
from app.core.db_models import AgentORM
from app.modules.projects.service import create_project


@pytest.mark.asyncio
async def test_create_project_founds_all_three_roles_with_default_profiles(harness):
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock")

    async with harness.session_factory() as session:
        result = await session.execute(select(AgentORM).where(AgentORM.project_id == project.id))
        rows = list(result.scalars().all())

    assert len(rows) == 3
    roles = {row.role for row in rows}
    assert roles == {"pm", "engineer", "reviewer"}

    for row in rows:
        profile = AgentProfile.model_validate(row.profile)
        assert profile.personality == Personality.PROFESSIONAL
        assert profile.working_style == WorkingStyle.BALANCED
        assert profile.decision_style == DecisionStyle.BALANCED
        assert profile.custom_instructions == ""
        assert profile.model_ref is None
        assert profile.role == row.role
