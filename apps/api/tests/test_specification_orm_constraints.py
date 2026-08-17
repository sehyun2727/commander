"""Sprint 12 §5.3 domain-layer concurrency guarantees, exercised directly
against the ORM/schema before any orchestrator/service code exists (Phase 1
of the sprint). These prove the *database* -- not a service-layer
check-then-insert -- is what makes:

* one active (non-terminal) Specification per project (`ActiveSpecificationLockORM`)
* one row per (specification, version) (`uq_spec_version`)
* one row per (specification, turn_index) (`uq_spec_turn_index`)

race-safe, mirroring the same DB-backed-constraint pattern Sprint 11 already
established for `role_singleton_locks` (see test_employee_singleton.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.db_models import (
    ActiveSpecificationLockORM,
    SpecificationORM,
    SpecificationTurnORM,
    SpecificationVersionORM,
)
from app.modules.projects.service import create_project


async def _make_project(harness):
    return await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )


async def _make_specification(harness, project_id: str) -> SpecificationORM:
    spec = SpecificationORM(project_id=project_id, request_text="Build a widget")
    async with harness.session_factory() as session:
        session.add(spec)
        await session.commit()
        await session.refresh(spec)
    return spec


@pytest.mark.asyncio
async def test_only_one_active_specification_lock_per_project(harness):
    project = await _make_project(harness)
    spec_a = await _make_specification(harness, project.id)
    spec_b = await _make_specification(harness, project.id)

    async with harness.session_factory() as session:
        session.add(ActiveSpecificationLockORM(project_id=project.id, specification_id=spec_a.id))
        await session.commit()

    with pytest.raises(IntegrityError):
        async with harness.session_factory() as session:
            session.add(ActiveSpecificationLockORM(project_id=project.id, specification_id=spec_b.id))
            await session.commit()


@pytest.mark.asyncio
async def test_specification_version_numbers_are_unique_per_specification(harness):
    project = await _make_project(harness)
    spec = await _make_specification(harness, project.id)

    version_kwargs = dict(
        specification_id=spec.id,
        version=1,
        title="v1",
        goals=[],
        non_goals=[],
        requirements=[],
        acceptance_criteria=[],
        architecture_components=[],
        risks=[],
        dependencies=[],
        assumptions=[],
        unresolved_questions=[],
        implementation_stages=[],
    )

    async with harness.session_factory() as session:
        session.add(SpecificationVersionORM(**version_kwargs))
        await session.commit()

    with pytest.raises(IntegrityError):
        async with harness.session_factory() as session:
            session.add(SpecificationVersionORM(**{**version_kwargs, "title": "v1 again"}))
            await session.commit()


@pytest.mark.asyncio
async def test_specification_turn_indexes_are_unique_per_specification(harness):
    project = await _make_project(harness)
    spec = await _make_specification(harness, project.id)

    turn_kwargs = dict(
        specification_id=spec.id,
        turn_index=1,
        actor_role="employee",
        kind="analysis",
        text="Initial PM analysis",
    )

    async with harness.session_factory() as session:
        session.add(SpecificationTurnORM(**turn_kwargs))
        await session.commit()

    with pytest.raises(IntegrityError):
        async with harness.session_factory() as session:
            session.add(SpecificationTurnORM(**{**turn_kwargs, "text": "duplicate index"}))
            await session.commit()


@pytest.mark.asyncio
async def test_a_different_project_can_hold_its_own_active_lock(harness):
    """The lock is scoped per-project, not global -- two different Companies
    must each be able to have their own in-flight Specification."""
    project_a = await _make_project(harness)
    project_b = await _make_project(harness)
    spec_a = await _make_specification(harness, project_a.id)
    spec_b = await _make_specification(harness, project_b.id)

    async with harness.session_factory() as session:
        session.add(ActiveSpecificationLockORM(project_id=project_a.id, specification_id=spec_a.id))
        session.add(ActiveSpecificationLockORM(project_id=project_b.id, specification_id=spec_b.id))
        await session.commit()
