from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import select

from app.core.contracts import AgentProfile
from app.core.db_models import AgentORM
from app.modules.projects.service import create_project
from app.templates import TEMPLATE
from app.templates.software_company import PM, RoleSpec


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
        assert profile == AgentProfile(**role.default_profile)


def test_role_order_is_pm_then_engineer_then_reviewer():
    assert [role.key for role in TEMPLATE.roles] == ["pm", "engineer", "reviewer"]


def test_reviewer_contract_requires_sections_before_verdict():
    contract = TEMPLATE.roles_by_key["reviewer"].contract
    for label in ("Problem", "Recommendation", "Risk", "Impact", "Verdict"):
        assert f"**{label}:**" in contract


# --- Sprint 10 Phase 1: RoleSpec as first-class data ------------------


def test_role_spec_is_frozen():
    """RoleSpec instances must be immutable -- a Role is a template-owned
    position, not mutable state (CLAUDE.md §2.3, Rule #16)."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        PM.title = "Product Manager"  # type: ignore[misc]


def test_leadership_roles_are_singletons_worker_roles_are_not():
    assert TEMPLATE.roles_by_key["pm"].singleton is True
    assert TEMPLATE.roles_by_key["pm"].category == "leadership"
    assert TEMPLATE.roles_by_key["reviewer"].singleton is True
    assert TEMPLATE.roles_by_key["reviewer"].category == "leadership"
    assert TEMPLATE.roles_by_key["engineer"].singleton is False
    assert TEMPLATE.roles_by_key["engineer"].category == "worker"


def test_role_spec_is_the_canonical_source_no_duplicate_dicts():
    """A role's model_ref/contract must live only on RoleSpec -- no second
    module-level dict may duplicate the same fact (Sprint 10 brief §7)."""
    for stale_field in ("model_ref_for_role", "role_contracts", "default_profiles"):
        assert not hasattr(TEMPLATE, stale_field)


def test_default_profile_is_read_only_and_derived():
    profile = PM.default_profile
    assert profile == {"name": "Priya Shah", "role": "pm"}
    with pytest.raises(TypeError):
        profile["name"] = "Someone Else"  # type: ignore[index]


def test_default_profile_reflects_role_identity_not_a_stored_copy():
    """default_profile is computed from founding_name/key, not a second
    stored value -- two RoleSpecs with the same identity fields produce
    equal default_profiles."""
    clone = dataclasses.replace(PM, title="Duplicate PM")
    assert clone.default_profile == PM.default_profile
    assert isinstance(clone, RoleSpec)
