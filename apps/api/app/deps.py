"""FastAPI dependency accessors for the singletons built in main.py's
lifespan (event bus, agent runtime, workflow engine, secrets provider,
DB session factory). Kept here so route modules don't import main.py."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from .core.db_models import UserORM
from .core.interfaces.agent_runtime import AgentRuntime
from .core.interfaces.event_bus import EventBus
from .core.interfaces.sandbox import SandboxRunner
from .core.interfaces.workflow_engine import WorkflowEngine
from .core.interfaces.workspace_manager import WorkspaceManager
from .core.secrets import SecretsProvider


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_agent_runtime(request: Request) -> AgentRuntime:
    return request.app.state.agent_runtime


def get_workflow_engine(request: Request) -> WorkflowEngine:
    return request.app.state.workflow_engine


def get_secrets(request: Request) -> SecretsProvider:
    return request.app.state.secrets


def get_workspace_manager(request: Request) -> WorkspaceManager:
    return request.app.state.workspace_manager


def get_sandbox_runner(request: Request) -> SandboxRunner:
    return request.app.state.sandbox_runner


def get_session_factory(request: Request):
    return request.app.state.session_factory


async def get_current_user(request: Request, session_factory=Depends(get_session_factory)) -> UserORM:
    # Imported here, not at module level: modules.auth.routes imports this
    # module for get_session_factory, so a top-level `from .modules.auth
    # import service` would cycle back into deps before it finishes
    # defining itself.
    from .modules.auth import service as auth_service

    token = request.cookies.get(auth_service.SESSION_COOKIE_NAME)
    user = await auth_service.resolve_session(session_factory, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user
