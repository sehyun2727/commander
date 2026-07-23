"""Seed a demo Commander company: "Acme AI".

Resets the local dev database and drives the *real* service layer (not raw
SQL) to build up a realistic history — a completed mission, a mission that
needed a round of changes before landing, a rejected mission, one already
sitting at a CEO Decision, and one still in the Backlog — so `make dev`
opens straight into a company that looks lived-in.

Run with the API's own venv: `apps/api/.venv/bin/python scripts/seed.py`
(or `make seed`, which does this for you).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"

# The API's config points at a DB path relative to the process cwd
# (`sqlite+aiosqlite:///./commander.db`), matching how `make dev` runs
# uvicorn from apps/api. Match that here so the seed lands in the same
# file the dev server reads.
os.chdir(API_DIR)
sys.path.insert(0, str(API_DIR))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_models import Base  # noqa: E402
from app.core.lifecycle.task_states import TaskState  # noqa: E402
from app.core.secrets import DBSecretsProvider  # noqa: E402
from app.modules.agent_runtime import DBAgentRuntime  # noqa: E402
from app.modules.approvals import service as approvals_service  # noqa: E402
from app.modules.event_bus import InProcessEventBus  # noqa: E402
from app.modules.projects import service as projects_service  # noqa: E402
from app.modules.tasks import service as tasks_service  # noqa: E402
from app.modules.workflow_engine import CommanderWorkflowEngine  # noqa: E402


async def wait_for_state(session_factory, task_id: str, *states: TaskState, timeout: float = 35.0) -> None:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(session_factory, task_id)
        if task.state in target:
            return
        await asyncio.sleep(0.1)
    raise RuntimeError(f"mission {task_id} never reached {target} within {timeout}s")


async def run_to_decision(
    session_factory, event_bus, agent_runtime, workflow_engine, project_id, title, description, priority
):
    task = await tasks_service.create_task(session_factory, event_bus, project_id, title, description, priority)
    await tasks_service.assign_task(session_factory, event_bus, agent_runtime, workflow_engine, task.id, None)
    await wait_for_state(session_factory, task.id, TaskState.PENDING_APPROVAL)
    return task


async def main() -> None:
    db_path = API_DIR / "commander.db"
    if db_path.exists():
        db_path.unlink()
        print(f"Removed existing dev database at {db_path}")

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    secrets = DBSecretsProvider(session_factory)
    event_bus = InProcessEventBus(session_factory)
    agent_runtime = DBAgentRuntime(session_factory, event_bus)
    workflow_engine = CommanderWorkflowEngine(session_factory, event_bus, agent_runtime, secrets)

    project = await projects_service.create_project(
        session_factory, event_bus, agent_runtime, name="Acme AI", provider="mock"
    )
    print(f"Founded company 'Acme AI' ({project.id})")

    # 1. A mission that sails straight through and gets approved.
    login = await run_to_decision(
        session_factory, event_bus, agent_runtime, workflow_engine, project.id,
        "Build login page", "Add email/password login with validation", "normal",
    )
    approval = (await approvals_service.list_pending(session_factory, project.id))[0]
    await approvals_service.decide(session_factory, workflow_engine, approval.id, "approve", "Ship it.")
    await wait_for_state(session_factory, login.id, TaskState.COMPLETED)
    await tasks_service.post_message(session_factory, event_bus, secrets, login.id, "Nice work on this one.")
    print("  - 'Build login page' -> approved -> Completed")

    # 2. A mission that needed one round of changes before it landed.
    ci = await run_to_decision(
        session_factory, event_bus, agent_runtime, workflow_engine, project.id,
        "Set up CI pipeline", "Run lint + tests on every push", "normal",
    )
    approval = (await approvals_service.list_pending(session_factory, project.id))[0]
    await approvals_service.decide(
        session_factory, workflow_engine, approval.id, "request_changes", "Please also cache dependencies."
    )
    await wait_for_state(session_factory, ci.id, TaskState.PENDING_APPROVAL)
    approval = (await approvals_service.list_pending(session_factory, project.id))[0]
    await approvals_service.decide(session_factory, workflow_engine, approval.id, "approve", "Much better.")
    await wait_for_state(session_factory, ci.id, TaskState.COMPLETED)
    print("  - 'Set up CI pipeline' -> changes requested -> approved -> Completed")

    # 3. A mission the CEO rejected outright.
    risky = await run_to_decision(
        session_factory, event_bus, agent_runtime, workflow_engine, project.id,
        "Delete prod DB", "\"Just to clean things up\"", "high",
    )
    approval = (await approvals_service.list_pending(session_factory, project.id))[0]
    await approvals_service.decide(session_factory, workflow_engine, approval.id, "reject", "Absolutely not.")
    await wait_for_state(session_factory, risky.id, TaskState.CANCELLED)
    print("  - 'Delete prod DB' -> rejected -> Cancelled")

    # 4. A mission sitting at a CEO Decision right now, ready for the demo.
    await run_to_decision(
        session_factory, event_bus, agent_runtime, workflow_engine, project.id,
        "Add search bar", "Let users search across their missions", "low",
    )
    print("  - 'Add search bar' -> awaiting a CEO Decision")

    # 5. A mission still in the Backlog, unassigned.
    await tasks_service.create_task(
        session_factory, event_bus, project.id,
        "Migrate to microservices", "Investigate splitting the API into services", "low",
    )
    print("  - 'Migrate to microservices' -> Backlog, unassigned")

    await engine.dispose()
    print(f"\nSeed complete. Run `make dev`, then open http://localhost:3000/company/{project.id}")


if __name__ == "__main__":
    asyncio.run(main())
