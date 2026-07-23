"""Per-Company, per-role model overrides.

Stored in the generic `settings_kv` table (same mechanism Company Settings
already uses for secrets) rather than a new column/table — one CEO-editable
string per (project, role), no schema migration needed.
"""

from __future__ import annotations

from ...core.db_models import SettingORM


def _key(project_id: str, role: str) -> str:
    return f"model_override:{project_id}:{role}"


async def get_override(session_factory, project_id: str, role: str) -> str | None:
    async with session_factory() as session:
        row = await session.get(SettingORM, _key(project_id, role))
        return row.value if row else None


async def set_override(session_factory, project_id: str, role: str, model_id: str) -> None:
    async with session_factory() as session:
        key = _key(project_id, role)
        row = await session.get(SettingORM, key)
        if row is None:
            session.add(SettingORM(key=key, value=model_id))
        else:
            row.value = model_id
        await session.commit()
