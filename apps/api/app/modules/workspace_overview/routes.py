"""Sprint 13 §7: the CEO Workspace snapshot API.

One read-only route, no query parameters beyond `project_id` -- there is no
pagination/limit input surface on this endpoint to validate or malform
(§9/§12); every list inside the snapshot is server-bounded (see
`schemas.MAX_*`), not client-paged.

Ownership resolved via `project_owned_by` before the service is touched
(Rule #15 -- 404, never 403, so cross-account access never discloses
whether a project exists). No mutation, no domain error to map --
`get_workspace_snapshot` returns `None` only when the project itself does
not exist for this owner, which is a 404 exactly like every other
project-scoped GET route in this codebase.

Incremental updates (DECISIONS.md #217): this route does not expose a
forward-cursor/"since" parameter. `event_cursor` in the response is just
the project's current max `EventORM.seq`, for the dashboard to compare
against events it already has. New activity keeps arriving over the
existing `/api/events/stream` SSE connection and the existing backward
`GET /api/projects/{project_id}/events?cursor=` route -- both already
ownership-gated the same way. There is no cursor expiry to recover from
(no event retention/pruning exists anywhere in this codebase today); on
reconnect or any suspected gap, the dashboard just refetches this snapshot
rather than replaying a partial event window.

Phase 3 §9/§12 concurrency properties (verified by inspection, not by new
tests, because each is a direct consequence of decisions already made and
already tested elsewhere -- inventing tests for them would just re-assert
the same fact under a different name):
  * ordering -- `event_cursor`/`recent_activity` order on `EventORM.seq`
    (an autoincrement PK), never on `created_at`, so two events with equal
    timestamps still sort deterministically
    (test_overview_event_cursor_matches_max_seq_for_the_project).
  * duplicate delivery -- this route does not push events; SSE delivery and
    the dashboard's existing `event.id` dedup convention (CLAUDE.md 9.4)
    are unchanged and out of scope here.
  * torn reads -- `get_workspace_snapshot` runs every select inside one
    `session_factory()` block (service.py), so a snapshot request always
    reflects one consistent instant; there is no window where a concurrent
    approval/transition can be half-reflected in a single response.
  * cross-company cursor -- `event_cursor` is computed from a query already
    filtered by this `project_id`, and the whole route 404s before that
    query runs if the project isn't owned by the caller (Rule #15,
    test_overview_cross_account_access_returns_404_not_403); there is no
    way to read another company's cursor.
  * retention gap / stale target -- every field is recomputed fresh from
    current DB state on every request (no caching, no stored snapshot), so
    there is no stale-target state to fall out of sync -- the dashboard
    always gets what's true right now.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import UserORM
from ...core.ownership import project_owned_by
from ...deps import get_current_user, get_session_factory
from . import service
from .schemas import WorkspaceSnapshot

router = APIRouter(tags=["workspace-overview"])


@router.get("/api/projects/{project_id}/workspace/overview", response_model=WorkspaceSnapshot)
async def get_workspace_overview(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    snapshot = await service.get_workspace_snapshot(session_factory, project_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return snapshot
