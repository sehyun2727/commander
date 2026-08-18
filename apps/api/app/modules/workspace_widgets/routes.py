"""Sprint 15 §6: CEO Workspace widget registry and preference routes.

Ownership resolved via `project_owned_by` before any service call (Rule
#15 -- 404, never 403). User identity always comes from `get_current_user`
(session cookie), never a client-supplied id (§8) -- preferences are
scoped to (this authenticated user, this owned company), so one CEO can
never read or write another's layout even for a company they both happen
to own in different accounts (accounts are already 1:1 with companies in
this codebase, but the scoping is enforced structurally regardless).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.errors import StaleRevisionError
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_session_factory
from . import service
from .registry import WIDGETS
from .schemas import WidgetDefinitionResponse, WorkspacePreferences, WorkspacePreferencesUpdateRequest
from .service import (
    DuplicateWidgetError,
    MissingWidgetError,
    RequiredWidgetHiddenError,
    UnknownWidgetError,
)

router = APIRouter(prefix="/api/projects/{project_id}/workspace", tags=["workspace-widgets"])


@router.get("/widgets", response_model=list[WidgetDefinitionResponse])
async def list_widgets(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return list(WIDGETS)


@router.get("/preferences", response_model=WorkspacePreferences)
async def get_preferences(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.get_effective_preferences(session_factory, user.id, project_id)


@router.put("/preferences", response_model=WorkspacePreferences)
async def update_preferences(
    project_id: str,
    body: WorkspacePreferencesUpdateRequest,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        return await service.update_preferences(
            session_factory, user.id, project_id, body.expected_revision, body.widgets
        )
    except (DuplicateWidgetError, UnknownWidgetError, MissingWidgetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RequiredWidgetHiddenError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StaleRevisionError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "stale_revision", "current_revision": exc.current_revision}
        )


@router.post("/preferences/reset", response_model=WorkspacePreferences)
async def reset_preferences(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.reset_preferences(session_factory, user.id, project_id)
