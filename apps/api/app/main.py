"""Commander API entrypoint: wires the singletons (DB, EventBus,
AgentRuntime, WorkflowEngine, SecretsProvider) into app.state during
startup and mounts every module's router. No AI/business logic lives here
— it only wires ports to concrete implementations, per
docs/ARCHITECTURE.md § API Server."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.db import async_session_factory, init_db
from .core.secrets import DBSecretsProvider
from .modules.agent_runtime import DBAgentRuntime
from .modules.agent_runtime import router as agents_router
from .modules.approvals import router as approvals_router
from .modules.event_bus import InProcessEventBus
from .modules.projects import router as projects_router
from .modules.realtime import router as realtime_router
from .modules.tasks import router as tasks_router
from .modules.timeline import router as timeline_router
from .modules.workflow_engine import CommanderWorkflowEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    session_factory = async_session_factory
    secrets = DBSecretsProvider(session_factory)
    event_bus = InProcessEventBus(session_factory)
    agent_runtime = DBAgentRuntime(session_factory, event_bus)
    workflow_engine = CommanderWorkflowEngine(session_factory, event_bus, agent_runtime, secrets)

    app.state.session_factory = session_factory
    app.state.secrets = secrets
    app.state.event_bus = event_bus
    app.state.agent_runtime = agent_runtime
    app.state.workflow_engine = workflow_engine

    yield


app = FastAPI(title="Commander API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(approvals_router)
app.include_router(timeline_router)
app.include_router(agents_router)
app.include_router(realtime_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
