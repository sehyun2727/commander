from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.contracts import AgentProfile
from app.core.db_models import AgentORM
from app.modules.projects.service import create_project
from app.templates import TEMPLATE


@pytest.mark.asyncio
async def test_founding_matches_the_template_exactly(harness):
    """Sprint 4.7 §10.6: founding must read the trio/order/profiles from
    the template, byte-for-byte identical to the pre-refactor hardcoded
    values (see test_founding_profiles.py, which this complements)."""
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)

    async with harness.session_factory() as session:
        result = await session.execute(select(AgentORM).where(AgentORM.project_id == project.id))
        rows = {row.role: row for row in result.scalars().all()}

    assert set(rows.keys()) == {role.key for role in TEMPLATE.roles}
    for role in TEMPLATE.roles:
        row = rows[role.key]
        assert row.name == role.founding_name
        assert row.avatar_color == role.avatar_color
        profile = AgentProfile.model_validate(row.profile)
        assert profile == TEMPLATE.default_profiles[role.key]


def test_role_order_is_pm_then_engineer_then_reviewer():
    assert [role.key for role in TEMPLATE.roles] == ["pm", "engineer", "reviewer"]


def test_reviewer_contract_requires_sections_before_verdict():
    contract = TEMPLATE.role_contracts["reviewer"]
    for label in ("Problem", "Recommendation", "Risk", "Impact", "Verdict"):
        assert f"**{label}:**" in contract
