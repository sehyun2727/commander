from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db_models import Base
from app.core.secrets import DBSecretsProvider
from app.modules.agent_runtime import DBAgentRuntime
from app.modules.event_bus import InProcessEventBus
from app.modules.workflow_engine import CommanderWorkflowEngine


class Harness:
    """A fully-wired backend stack (DB + EventBus + AgentRuntime +
    WorkflowEngine + Secrets) against an isolated temp-file sqlite DB, so
    tests never touch the dev database and never need a running server."""

    def __init__(self, session_factory, event_bus, agent_runtime, workflow_engine, secrets) -> None:
        self.session_factory = session_factory
        self.event_bus = event_bus
        self.agent_runtime = agent_runtime
        self.workflow_engine = workflow_engine
        self.secrets = secrets


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
    workflow_engine = CommanderWorkflowEngine(session_factory, event_bus, agent_runtime, secrets)

    yield Harness(session_factory, event_bus, agent_runtime, workflow_engine, secrets)

    await engine.dispose()
