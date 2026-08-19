"""Commander API entrypoint: wires the singletons (DB, EventBus,
AgentRuntime, WorkflowEngine, SecretsProvider) into app.state during
startup and mounts every module's router. No AI/business logic lives here
— it only wires ports to concrete implementations, per
docs/ARCHITECTURE.md § API Server."""

from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .core.boot_checks import (
    BootConfigError,
    git_sha,
    redact_database_url,
    validate_boot_config,
    validate_db_revision,
)
from .core.config import settings
from .core.db import async_session_factory, engine, init_db
from .core.logging import install_logging, request_id_var
from .core.secrets import DBSecretsProvider

logger = logging.getLogger("commander")
from .modules.agent_profiles import router as agent_profiles_router
from .modules.agent_runtime import DBAgentRuntime
from .modules.agent_runtime import router as agents_router
from .modules.approvals import router as approvals_router
from .modules.auth import router as auth_router
from .modules.costs import router as costs_router
from .modules.event_bus import InProcessEventBus
from .modules.memory import install_memory_subscribers
from .modules.model_registry import router as models_router
from .modules.planning import router as planning_router
from .modules.projects import router as projects_router
from .modules.realtime import router as realtime_router
from .modules.reports import router as reports_router
from .modules.sandbox import DockerSandbox
from .modules.sandbox import router as sandbox_router
from .modules.situation import router as situation_router
from .modules.skill_templates import router as skill_templates_router
from .modules.tasks import recover_orphaned_tasks
from .modules.tasks import router as tasks_router
from .modules.timeline import router as timeline_router
from .modules.workflow_engine import CommanderWorkflowEngine
from .modules.workspace_manager import LocalGitWorkspaceManager
from .modules.workspace_manager import router as workspace_router
from .modules.workspace_overview import router as workspace_overview_router
from .modules.workspace_widgets import router as workspace_widgets_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_logging()
    print(f"Commander booting: git={git_sha()}", file=sys.stderr)

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

    try:
        await validate_db_revision(engine, settings.database_url)
    except BootConfigError as exc:
        print(f"Commander cannot start: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    session_factory = async_session_factory
    secrets = DBSecretsProvider(session_factory)
    event_bus = InProcessEventBus(session_factory)
    install_memory_subscribers(event_bus, session_factory)
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


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Server-issued UUID per request (Sprint 19 §7.1) -- NEVER trusts an
    incoming X-Request-Id header (a client-supplied ID could be forged to
    make unrelated requests appear correlated in the logs). Registered
    before CORSMiddleware so the correlation ID covers the whole request,
    including CORS's own preflight/rejection handling."""
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        request_id_var.reset(token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Rule #18 (no silent failure): a bug the code never anticipated
    still has to end as something the CEO's screen can show, not a blank
    failure. Starlette's ServerErrorMiddleware -- which drives this
    handler -- sits *outside* CORSMiddleware in the stack (see
    starlette.applications.Starlette.build_middleware_stack), so it never
    gets CORS headers applied automatically; without adding them here by
    hand from the same origin allowlist CORSMiddleware uses, a real
    server crash reads in the browser as a CORS failure, exactly like the
    Sprint 9 stale-process incident this diagnosability work follows up
    on (sprint10.md §4.1a)."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    response = JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Something went wrong on Commander's end. Please try again "
                "in a moment; if it keeps happening, this has been logged."
            )
        },
    )
    origin = request.headers.get("origin")
    if origin in settings.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


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
app.include_router(skill_templates_router)
app.include_router(workspace_router)
app.include_router(workspace_overview_router)
app.include_router(workspace_widgets_router)
app.include_router(sandbox_router)
app.include_router(planning_router)


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
