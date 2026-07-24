"""Read-only queries over a company's git workspace, for the dashboard.

Pure lookups: confirms the company exists, then delegates to
`WorkspaceManager`. No AI-generated content is ever executed here.
"""

from __future__ import annotations

from ...core.db_models import ProjectORM
from ...core.interfaces.workspace_manager import FileEntry, MergeRecord, WorkspaceManager


async def project_exists(session_factory, project_id: str) -> bool:
    async with session_factory() as session:
        return await session.get(ProjectORM, project_id) is not None


async def get_tree(
    session_factory, workspace_manager: WorkspaceManager, project_id: str, ref: str
) -> list[FileEntry]:
    return await workspace_manager.list_tree(project_id, ref)


async def get_file(
    session_factory, workspace_manager: WorkspaceManager, project_id: str, path: str, ref: str
) -> str | None:
    try:
        return await workspace_manager.read_file(project_id, path, ref)
    except (FileNotFoundError, ValueError):
        return None


async def get_merges(
    session_factory, workspace_manager: WorkspaceManager, project_id: str, limit: int
) -> list[MergeRecord]:
    return await workspace_manager.recent_merges(project_id, limit)
