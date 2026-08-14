"""Sprint 10 Phase 2 §10: singleton enforcement for leadership Roles, and
the structural guarantee that worker Roles (Engineer) may hold more than
one Employee.

`create_employee` is not yet reachable from any route -- Sprint 11 wires
the hiring endpoint through it. These tests exercise the service function
directly against the harness DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db_models import AgentORM
from app.core.errors import SingletonRoleViolation
from app.modules.agent_runtime.service import create_employee
from app.modules.projects.service import create_project


@pytest.mark.asyncio
async def test_agent_orm_exposes_role_key_not_role(harness):
    """Sprint 10 §9.1: the column is `role_key`, referencing RoleSpec.key --
    not the old ad-hoc `role` string."""
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    async with harness.session_factory() as session:
        rows = (await session.execute(select(AgentORM).where(AgentORM.project_id == project.id))).scalars().all()

    assert {row.role_key for row in rows} == {"pm", "engineer", "reviewer"}
    assert not hasattr(AgentORM, "role")


@pytest.mark.asyncio
async def test_create_employee_rejects_a_second_pm(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(SingletonRoleViolation):
        await create_employee(harness.session_factory, project.id, "pm")


@pytest.mark.asyncio
async def test_create_employee_rejects_a_second_reviewer(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(SingletonRoleViolation):
        await create_employee(harness.session_factory, project.id, "reviewer")


@pytest.mark.asyncio
async def test_create_employee_allows_multiple_engineers(harness):
    """Sprint 10 §9.2/§10: worker Roles are not singletons -- a second (and
    third) Engineer Employee must be accepted, not rejected."""
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    second = await create_employee(harness.session_factory, project.id, "engineer")
    third = await create_employee(harness.session_factory, project.id, "engineer")

    assert second.id != third.id
    assert second.role_key == "engineer"
    assert third.role_key == "engineer"

    async with harness.session_factory() as session:
        engineers = (
            await session.execute(
                select(AgentORM).where(AgentORM.project_id == project.id, AgentORM.role_key == "engineer")
            )
        ).scalars().all()

    assert len(engineers) == 3


@pytest.mark.asyncio
async def test_create_employee_race_is_out_of_scope_for_this_sprint(harness):
    """Sprint 10 §10 requires either a DB-level unique constraint or a
    documented reason the service-layer check-then-insert is sufficient
    (docs/DECISIONS.md). `create_employee` is unreachable from any route
    this sprint -- Sprint 11 adds the hiring endpoint, at which point
    concurrent-request races become a real concern to revisit."""
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(SingletonRoleViolation):
        await create_employee(harness.session_factory, project.id, "pm")

    async with harness.session_factory() as session:
        pm_count = len(
            (
                await session.execute(
                    select(AgentORM).where(AgentORM.project_id == project.id, AgentORM.role_key == "pm")
                )
            )
            .scalars()
            .all()
        )
    assert pm_count == 1
