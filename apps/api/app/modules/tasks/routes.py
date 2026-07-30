from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.db_models import TaskORM, UserORM
from ...core.events.base import Event
from ...core.ownership import project_owned_by, resource_owned_by
from ...deps import (
    get_agent_runtime,
    get_current_user,
    get_event_bus,
    get_secrets,
    get_session_factory,
    get_workflow_engine,
    get_workspace_manager,
)
from . import service
from .schemas import (
    DiffResponse,
    MessageCreateRequest,
    TaskAssignRequest,
    TaskCancelRequest,
    TaskCreateRequest,
    TaskResponse,
)

router = APIRouter(prefix="/api", tags=["tasks"])


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse)
async def create_task(
    project_id: str,
    body: TaskCreateRequest,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.create_task(
        session_factory,
        event_bus,
        project_id,
        body.title,
        body.description,
        body.priority,
        body.deliverable_type,
    )


@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await project_owned_by(session_factory, project_id, user.id):
        raise HTTPException(status_code=404, detail="Company not found")
    return await service.list_tasks(session_factory, project_id)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    return await service.get_task(session_factory, task_id)


@router.get("/tasks/{task_id}/diff", response_model=DiffResponse)
async def get_diff(
    task_id: str,
    session_factory=Depends(get_session_factory),
    workspace_manager=Depends(get_workspace_manager),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    result = await service.get_diff(session_factory, workspace_manager, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No diff available for this mission")
    diff_text, truncated = result
    return DiffResponse(diff_text=diff_text, truncated=truncated)


@router.post("/tasks/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: str,
    body: TaskAssignRequest,
    event_bus=Depends(get_event_bus),
    agent_runtime=Depends(get_agent_runtime),
    workflow_engine=Depends(get_workflow_engine),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    task = await service.assign_task(
        session_factory, event_bus, agent_runtime, workflow_engine, task_id, body.agent_id
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: str,
    body: TaskCancelRequest,
    session_factory=Depends(get_session_factory),
    workflow_engine=Depends(get_workflow_engine),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    task = await service.get_task(session_factory, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    ok = await service.cancel_task(
        workflow_engine, task_id, body.reason or "CEO cancelled the mission"
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Mission cannot be cancelled from its current state")
    return await service.get_task(session_factory, task_id)


@router.get("/tasks/{task_id}/messages", response_model=list[Event])
async def list_messages(
    task_id: str,
    event_bus=Depends(get_event_bus),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    task = await service.get_task(session_factory, task_id)
    return await service.list_messages(event_bus, task.project_id, task_id)


@router.post("/tasks/{task_id}/messages", response_model=Event)
async def post_message(
    task_id: str,
    body: MessageCreateRequest,
    event_bus=Depends(get_event_bus),
    secrets=Depends(get_secrets),
    session_factory=Depends(get_session_factory),
    user: UserORM = Depends(get_current_user),
):
    if not await resource_owned_by(session_factory, TaskORM, task_id, user.id):
        raise HTTPException(status_code=404, detail="Mission not found")
    return await service.post_message(session_factory, event_bus, secrets, task_id, body.text)
