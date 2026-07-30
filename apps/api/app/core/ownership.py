"""Account-scoping choke point (Sprint 9, Rule #15).

Shared infra like db_models, not a module-to-module dependency -- every
project-scoped route resolves ownership through this one function so "the
company doesn't exist" and "it's not yours" always look identical: 404,
never 403. Other tables are scoped transitively through the project they
belong to (tasks.project_id, approvals.project_id, ...), never through a
second owner_id column of their own (brief §2.4).
"""

from __future__ import annotations

from .db_models import ProjectORM


async def project_owned_by(session_factory, project_id: str, owner_id: str) -> bool:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
        return project is not None and project.owner_id == owner_id


async def resource_owned_by(session_factory, orm_class: type, resource_id: str, owner_id: str) -> bool:
    """Same 404-not-403 guarantee as `project_owned_by`, for any row that
    carries a `project_id` column (tasks, approvals, agents, reports, cost
    entries, ...) instead of an `owner_id` of its own."""
    async with session_factory() as session:
        row = await session.get(orm_class, resource_id)
        if row is None:
            return False
        project = await session.get(ProjectORM, row.project_id)
        return project is not None and project.owner_id == owner_id
