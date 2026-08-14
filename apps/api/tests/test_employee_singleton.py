"""Sprint 10 Phase 2 §10 + Sprint 11 §4.10/§6.4: singleton enforcement for
leadership Roles, and the structural guarantee that worker Roles (Engineer)
may hold more than one Employee.

`hire_employee` (renamed from Sprint 10's `create_employee`) is now the one
authoritative hiring path, reachable from `POST /api/projects/{id}/agents`.
Sprint 10's non-atomic check-then-insert is no longer an acceptable
singleton guarantee on its own (docs/DECISIONS.md #167) -- these tests
exercise both the ordinary validation/rejection paths and a REAL
concurrency race (via asyncio.gather, not sequential calls) against the
DB-backed `role_singleton_locks` composite primary key.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db_models import AgentORM, RoleSingletonLockORM
from app.core.errors import SingletonRoleViolation
from app.modules.agent_runtime.service import (
    InvalidEmployeeNameError,
    InvalidModelRefError,
    InvalidRoleError,
    InvalidSkillTemplateError,
    hire_employee,
)
from app.modules.event_bus import InProcessEventBus
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
async def test_hire_employee_rejects_a_second_pm(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(SingletonRoleViolation):
        await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "pm", "Second PM")


@pytest.mark.asyncio
async def test_hire_employee_rejects_a_second_reviewer(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(SingletonRoleViolation):
        await hire_employee(
            harness.session_factory, harness.event_bus, project.id, "mock", "reviewer", "Second Reviewer"
        )


@pytest.mark.asyncio
async def test_hire_employee_allows_multiple_engineers(harness):
    """Sprint 10 §9.2/§10: worker Roles are not singletons -- a second (and
    third) Engineer Employee must be accepted, not rejected."""
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    second = await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "engineer", "Kim")
    third = await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "engineer", "Lee")

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
async def test_hire_employee_no_partial_row_on_singleton_violation(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(SingletonRoleViolation):
        await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "pm", "Second PM")

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


@pytest.mark.asyncio
async def test_hire_employee_succeeds_for_vacant_cto(harness):
    """Sprint 11 §6.9: CTO is a founding=False, singleton=True Role -- vacant
    at founding, hireable afterward, and claims its own lock row."""
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    cto = await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "cto", "Ada")
    assert cto.role_key == "cto"

    async with harness.session_factory() as session:
        lock = await session.get(RoleSingletonLockORM, (project.id, "cto"))
    assert lock is not None
    assert lock.agent_id == cto.id


@pytest.mark.asyncio
async def test_hire_employee_rejects_a_second_cto(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "cto", "Ada")
    with pytest.raises(SingletonRoleViolation):
        await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "cto", "Grace")


@pytest.mark.asyncio
async def test_hire_employee_rejects_unknown_role(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(InvalidRoleError):
        await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "astronaut", "Buzz")


@pytest.mark.asyncio
async def test_hire_employee_rejects_empty_name(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(InvalidEmployeeNameError):
        await hire_employee(harness.session_factory, harness.event_bus, project.id, "mock", "engineer", "   ")


@pytest.mark.asyncio
async def test_hire_employee_rejects_oversized_name(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(InvalidEmployeeNameError):
        await hire_employee(
            harness.session_factory, harness.event_bus, project.id, "mock", "engineer", "x" * 101
        )


@pytest.mark.asyncio
async def test_hire_employee_rejects_unknown_model_ref(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(InvalidModelRefError):
        await hire_employee(
            harness.session_factory,
            harness.event_bus,
            project.id,
            "mock",
            "engineer",
            "Kim",
            model_ref="not-a-real-model",
        )


@pytest.mark.asyncio
async def test_hire_employee_rejects_unknown_skill_template(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    with pytest.raises(InvalidSkillTemplateError):
        await hire_employee(
            harness.session_factory,
            harness.event_bus,
            project.id,
            "mock",
            "engineer",
            "Kim",
            skill_template_key="not-a-real-template",
        )


@pytest.mark.asyncio
async def test_hire_employee_persists_model_ref_and_skill_template(harness):
    project = await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )

    row = await hire_employee(
        harness.session_factory,
        harness.event_bus,
        project.id,
        "mock",
        "engineer",
        "Kim",
        skill_template_key="speed_focused",
    )

    assert row.profile["skill_template_key"] == "speed_focused"
    assert row.profile["name"] == "Kim"


@pytest.mark.asyncio
async def test_hire_employee_concurrent_hires_for_a_singleton_role_only_one_wins(tmp_path):
    """Sprint 11 §4.10: a genuine concurrency race, not a sequential
    check-then-insert simulation. Two `hire_employee` calls for the same
    singleton Role ("cto") fire concurrently via `asyncio.gather`; the
    database's own composite-PK uniqueness on `role_singleton_locks` --
    not a service-layer pre-check -- must guarantee exactly one winner.

    sqlite3's default connect `timeout` (5s, inherited by aiosqlite) makes a
    second writer block-and-retry against the first's lock instead of
    immediately raising `OperationalError: database is locked`, so the loser
    reliably surfaces as an `IntegrityError` -> `SingletonRoleViolation`
    rather than an unrelated locking error (see docs/DECISIONS.md)."""
    from app.core.db_models import Base
    from app.modules.agent_runtime import DBAgentRuntime
    from app.modules.auth import service as auth_service

    db_path = tmp_path / "concurrency.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False, connect_args={"timeout": 5})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    event_bus = InProcessEventBus(session_factory)
    agent_runtime = DBAgentRuntime(session_factory, event_bus)
    user = await auth_service.register(session_factory, "race-ceo@test.local", "testpassword123", "Race CEO")
    project = await create_project(session_factory, event_bus, agent_runtime, "Acme", "mock", owner_id=user.id)

    results = await asyncio.gather(
        hire_employee(session_factory, event_bus, project.id, "mock", "cto", "Ada"),
        hire_employee(session_factory, event_bus, project.id, "mock", "cto", "Grace"),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], SingletonRoleViolation)

    async with session_factory() as session:
        ctos = (
            await session.execute(select(AgentORM).where(AgentORM.project_id == project.id, AgentORM.role_key == "cto"))
        ).scalars().all()
        locks = (
            await session.execute(
                select(RoleSingletonLockORM).where(
                    RoleSingletonLockORM.project_id == project.id, RoleSingletonLockORM.role_key == "cto"
                )
            )
        ).scalars().all()

    assert len(ctos) == 1
    assert len(locks) == 1
    assert locks[0].agent_id == ctos[0].id

    await engine.dispose()
