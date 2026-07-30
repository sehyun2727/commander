from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db_models import Base
from app.core.secrets import DBSecretsProvider
from app.deps import (
    get_agent_runtime,
    get_event_bus,
    get_sandbox_runner,
    get_secrets,
    get_session_factory,
    get_workflow_engine,
    get_workspace_manager,
)
from app.main import app
from app.modules.agent_runtime import DBAgentRuntime
from app.modules.auth import service as auth_service
from app.modules.event_bus import InProcessEventBus
from app.modules.sandbox import FakeSandbox
from app.modules.workflow_engine import CommanderWorkflowEngine
from app.modules.workspace_manager import LocalGitWorkspaceManager

# Narrative pacing sleeps (0.5-1.5s per pipeline beat) are a production UX
# device with no test value -- they were solely responsible for a single
# full-pipeline test taking 15.7s and the suite taking ~230s. Flipped once
# at collection time since `settings` is a process-wide singleton.
settings.commander_pacing_enabled = False


class Harness:
    """A fully-wired backend stack (DB + EventBus + AgentRuntime +
    WorkflowEngine + WorkspaceManager + SandboxRunner + Secrets) against an
    isolated temp-file sqlite DB and temp-dir git workspaces, so tests
    never touch the dev database/workspaces and never need a running
    server or Docker."""

    def __init__(
        self,
        session_factory,
        event_bus,
        agent_runtime,
        workflow_engine,
        secrets,
        workspace_manager,
        sandbox_runner,
        user,
    ) -> None:
        self.session_factory = session_factory
        self.event_bus = event_bus
        self.agent_runtime = agent_runtime
        self.workflow_engine = workflow_engine
        self.secrets = secrets
        self.workspace_manager = workspace_manager
        self.sandbox_runner = sandbox_runner
        self.user = user


@pytest_asyncio.fixture
async def harness(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    secrets = DBSecretsProvider(session_factory)
    event_bus = InProcessEventBus(session_factory)
    agent_runtime = DBAgentRuntime(session_factory, event_bus)
    workspace_manager = LocalGitWorkspaceManager(str(tmp_path / "workspaces"))
    sandbox_runner = FakeSandbox()
    workflow_engine = CommanderWorkflowEngine(
        session_factory, event_bus, agent_runtime, secrets, workspace_manager, sandbox_runner
    )
    user = await auth_service.register(session_factory, "ceo@test.local", "testpassword123", "Test CEO")

    yield Harness(
        session_factory, event_bus, agent_runtime, workflow_engine, secrets, workspace_manager, sandbox_runner, user
    )

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(harness):
    """A real httpx client against the actual FastAPI app/routes (not the
    service layer directly) -- for exercising auth: cookies, 401s, and
    cross-account 404s, which only exist at the route layer. Bypasses
    main.py's lifespan (no real Postgres/Docker) by overriding every
    request.app.state.X dependency with the harness's own singletons."""
    app.dependency_overrides[get_session_factory] = lambda: harness.session_factory
    app.dependency_overrides[get_event_bus] = lambda: harness.event_bus
    app.dependency_overrides[get_agent_runtime] = lambda: harness.agent_runtime
    app.dependency_overrides[get_workflow_engine] = lambda: harness.workflow_engine
    app.dependency_overrides[get_secrets] = lambda: harness.secrets
    app.dependency_overrides[get_workspace_manager] = lambda: harness.workspace_manager
    app.dependency_overrides[get_sandbox_runner] = lambda: harness.sandbox_runner

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
