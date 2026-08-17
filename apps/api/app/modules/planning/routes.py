"""Sprint 12 §4/§8 Phase 3: the Project Specification API surface.

Every route resolves ownership through `core.ownership` before touching
`service` (Rule #15 -- 404, never 403). Domain failures raised by
`orchestrator`/`service` are named `CommanderError` subclasses (see
`core.errors`) or `InvalidTransition` (illegal `SpecificationStatus` move);
this module's only job is mapping each one to the right HTTP status, the
same pattern `tasks/routes.py` and `agent_runtime/routes.py` already use --
no generic exception-handling middleware (Rule #18: every CEO mutation
either succeeds or fails with a visible explanation).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import SpecificationORM, UserORM
from ...core.errors import (
    ActivePlanningExistsError,
    CTOVacantError,
    SpecificationAlreadyExecutingError,
)
from ...core.lifecycle.state_machine import InvalidTransition
from ...core.ownership import project_owned_by, resource_owned_by
from ...deps import (
    get_agent_runtime,
    get_current_user,
    get_event_bus,
    get_secrets,
    get_session_factory,
    get_workflow_engine,
)
from ..tasks import TaskResponse
from . import service
from .schemas import (
    SpecificationCancelRequest,
    SpecificationClarificationAnswerRequest,
    SpecificationRejectRequest,
    SpecificationResponse,
    SpecificationRevisionRequest,
    SpecificationStartRequest,
    SpecificationTurnResponse,
    SpecificationVersionResponse,
)

router = APIRouter(prefix="/api", tags=["planning"])


@router.post("/projects/{project_id}/specifications", response_model=SpecificationResponse)
async def start_planning(
    project_id: str,
    body: SpecificationStartRequest,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    secrets=Depends(get_secrets),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        return await service.start_planning(
            session_factory,
            event_bus,
            agent_runtime,
            secrets,
            project_id,
            body.request_text,
            source_task_id=body.source_task_id,
        )
    except CTOVacantError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ActivePlanningExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/specifications", response_model=list[SpecificationResponse])
async def list_specifications(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.list_specifications(session_factory, project_id)


@router.get("/specifications/{specification_id}", response_model=SpecificationResponse)
async def get_specification(
    specification_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    return await service.get_specification(session_factory, specification_id)


@router.get("/specifications/{specification_id}/turns", response_model=list[SpecificationTurnResponse])
async def list_turns(
    specification_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    return await service.list_turns(session_factory, specification_id)


@router.get("/specifications/{specification_id}/versions", response_model=list[SpecificationVersionResponse])
async def list_versions(
    specification_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    return await service.list_versions(session_factory, specification_id)


@router.post("/specifications/{specification_id}/clarification-answer", response_model=SpecificationResponse)
async def resume_after_clarification(
    specification_id: str,
    body: SpecificationClarificationAnswerRequest,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    secrets=Depends(get_secrets),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    try:
        return await service.resume_after_clarification(
            session_factory, event_bus, agent_runtime, secrets, specification_id, body.answers
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/specifications/{specification_id}/revision", response_model=SpecificationResponse)
async def submit_revision(
    specification_id: str,
    body: SpecificationRevisionRequest,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    secrets=Depends(get_secrets),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    try:
        return await service.submit_revision(
            session_factory, event_bus, agent_runtime, secrets, specification_id, body.feedback
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/specifications/{specification_id}/approve", response_model=SpecificationResponse)
async def approve_specification(
    specification_id: str,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    try:
        return await service.approve_specification(session_factory, event_bus, specification_id)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/specifications/{specification_id}/reject", response_model=SpecificationResponse)
async def reject_specification(
    specification_id: str,
    body: SpecificationRejectRequest,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    try:
        return await service.reject_specification(session_factory, event_bus, specification_id, body.reason)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/specifications/{specification_id}/cancel", response_model=SpecificationResponse)
async def cancel_planning(
    specification_id: str,
    body: SpecificationCancelRequest,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    secrets=Depends(get_secrets),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    ok = await service.cancel_planning(session_factory, event_bus, agent_runtime, secrets, specification_id, body.reason)
    if not ok:
        raise HTTPException(status_code=409, detail="Project Specification cannot be cancelled from its current state")
    return await service.get_specification(session_factory, specification_id)


@router.post("/specifications/{specification_id}/begin-execution", response_model=TaskResponse)
async def begin_execution(
    specification_id: str,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    workflow_engine=Depends(get_workflow_engine),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, SpecificationORM, specification_id, user.id):
        raise HTTPException(status_code=404, detail="Project Specification not found")
    try:
        return await service.begin_execution(
            session_factory, event_bus, agent_runtime, workflow_engine, specification_id
        )
    except SpecificationAlreadyExecutingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
