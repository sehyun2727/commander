"""FastAPI dependency accessors for the singletons built in main.py's
lifespan (event bus, agent runtime, workflow engine, secrets provider,
DB session factory). Kept here so route modules don't import main.py."""

from __future__ import annotations

from fastapi import Request

from .core.interfaces.agent_runtime import AgentRuntime
from .core.interfaces.event_bus import EventBus
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


def get_session_factory(request: Request):
    return request.app.state.session_factory
