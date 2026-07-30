"""Commander API entrypoint: wires the singletons (DB, EventBus,
AgentRuntime, WorkflowEngine, SecretsProvider) into app.state during
startup and mounts every module's router. No AI/business logic lives here
— it only wires ports to concrete implementations, per
docs/ARCHITECTURE.md § API Server."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .core.boot_checks import BootConfigError, redact_database_url, validate_boot_config
from .core.config import settings
from .core.db import async_session_factory, init_db
from .core.secrets import DBSecretsProvider
from .modules.agent_profiles import router as agent_profiles_router
from .modules.agent_runtime import DBAgentRuntime
from .modules.agent_runtime import router as agents_router
from .modules.approvals import router as approvals_router
from .modules.auth import router as auth_router
from .modules.costs import router as costs_router
from .modules.event_bus import InProcessEventBus
from .modules.model_registry import router as models_router
from .modules.projects import router as projects_router
from .modules.realtime import router as realtime_router
from .modules.reports import router as reports_router
from .modules.sandbox import DockerSandbox
from .modules.sandbox import router as sandbox_router
from .modules.situation import router as situation_router
from .modules.tasks import recover_orphaned_tasks
from .modules.tasks import router as tasks_router
from .modules.timeline import router as timeline_router
from .modules.workflow_engine import CommanderWorkflowEngine
from .modules.workspace_manager import LocalGitWorkspaceManager
from .modules.workspace_manager import router as workspace_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_boot_config()
    except BootConfigError as exc:
        print(f"Commander cannot start: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    try:
        await init_db()
    except Exception as exc:
        print(
            f"Commander cannot start: could not reach the database "
            f"({redact_database_url(settings.database_url)}): {exc}. "
            "Is Postgres running? Try `make db-up`.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    session_factory = async_session_factory
    secrets = DBSecretsProvider(session_factory)
    event_bus = InProcessEventBus(session_factory)
    agent_runtime = DBAgentRuntime(session_factory, event_bus)
    workspace_manager = LocalGitWorkspaceManager(settings.commander_workspace_root)
    sandbox_runner = DockerSandbox(settings.commander_sandbox_image)
    workflow_engine = CommanderWorkflowEngine(
        session_factory, event_bus, agent_runtime, secrets, workspace_manager, sandbox_runner
    )

    app.state.session_factory = session_factory
    app.state.secrets = secrets
    app.state.event_bus = event_bus
    app.state.agent_runtime = agent_runtime
    app.state.workspace_manager = workspace_manager
    app.state.sandbox_runner = sandbox_runner
    app.state.workflow_engine = workflow_engine

    # Orphan mission recovery (Sprint 9): any Mission still mid-pipeline
    # when the process last stopped had its background asyncio.Task die
    # with it -- nothing in this fresh process will ever move it again, so
    # it gets recovered to `blocked` before the API starts serving traffic.
    await recover_orphaned_tasks(session_factory, event_bus)

    yield


app = FastAPI(title="Commander API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(approvals_router)
app.include_router(timeline_router)
app.include_router(agents_router)
app.include_router(agent_profiles_router)
app.include_router(realtime_router)
app.include_router(costs_router)
app.include_router(models_router)
app.include_router(reports_router)
app.include_router(situation_router)
app.include_router(workspace_router)
app.include_router(sandbox_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness only -- no dependencies, always 200 once the process is up."""
    return {"status": "ok"}


@app.get("/api/health/db")
async def health_db() -> JSONResponse:
    """Readiness: does a real round-trip against the configured database.
    Never raises past this handler -- a down Postgres should read as a
    clear 503 to whatever's polling this (deploy tooling, the dashboard's
    API-down banner), not a bare connection-refused traceback."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": f"database unreachable: {exc}"},
        )
    return JSONResponse(status_code=200, content={"status": "ok"})
