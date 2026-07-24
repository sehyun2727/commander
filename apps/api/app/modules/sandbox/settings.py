"""Per-Company execution toggle (Sprint 6 Phase 2).

Stored in the generic `settings_kv` table -- same mechanism
`model_registry.overrides` already uses for per-role model overrides --
rather than a new `ProjectORM` column, so no schema migration is needed.
Unset means enabled: a company that has never touched this setting gets
execution by default, matching "the product must fully work" without any
CEO configuration step.
"""

from __future__ import annotations

from ...core.db_models import SettingORM


def _key(project_id: str) -> str:
    return f"execution_enabled:{project_id}"


async def get_execution_enabled(session_factory, project_id: str) -> bool:
    async with session_factory() as session:
        row = await session.get(SettingORM, _key(project_id))
        return row.value != "false" if row else True


async def set_execution_enabled(session_factory, project_id: str, enabled: bool) -> None:
    async with session_factory() as session:
        key = _key(project_id)
        value = "true" if enabled else "false"
        row = await session.get(SettingORM, key)
        if row is None:
            session.add(SettingORM(key=key, value=value))
        else:
            row.value = value
        await session.commit()
