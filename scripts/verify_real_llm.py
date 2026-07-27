"""One-command real-LLM smoke test: drives a full Mission through a real
Anthropic PM -> Engineer -> Reviewer pipeline and reports pass/fail.

Exercises exactly what Sprint 7 Phase 3 needs verified against real (not
mock) model output: the request actually reaches Anthropic, the trailing
**Verdict:** line still parses, a missing/invalid key surfaces as a
plain-language error instead of a traceback, and real token usage becomes
a real USD cost. Safe to run repeatedly -- everything happens in a
throwaway SQLite database and workspace directory, never touching the
project's own dev database or git history.

Usage: `make verify-llm` or `apps/api/.venv/bin/python scripts/verify_real_llm.py`
Requires ANTHROPIC_API_KEY to be set (in the repo-root .env or the
environment) -- exits early with a plain-language message if it isn't.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_models import Base  # noqa: E402
from app.core.events import EventType  # noqa: E402
from app.core.lifecycle.task_states import TaskState  # noqa: E402
from app.core.secrets import DBSecretsProvider  # noqa: E402
from app.modules.agent_runtime import DBAgentRuntime  # noqa: E402
from app.modules.approvals import service as approvals_service  # noqa: E402
from app.modules.costs import service as costs_service  # noqa: E402
from app.modules.event_bus import InProcessEventBus  # noqa: E402
from app.modules.projects import service as projects_service  # noqa: E402
from app.modules.sandbox import DockerSandbox  # noqa: E402
from app.modules.tasks import service as tasks_service  # noqa: E402
from app.modules.workflow_engine import CommanderWorkflowEngine  # noqa: E402
from app.modules.workflow_engine.parsing import parse_verdict  # noqa: E402
from app.modules.workspace_manager import LocalGitWorkspaceManager  # noqa: E402

_TIMEOUT_SECONDS = 120.0


async def wait_for_state(session_factory, task_id: str, *states: TaskState, timeout: float) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.5)
    raise TimeoutError(f"mission {task_id} never reached {target} within {timeout}s")


async def main() -> int:
    if not settings.anthropic_api_key:
        print(
            "FAIL: no ANTHROPIC_API_KEY configured.\n"
            "Set it in the repo-root .env (see .env.example), or export it in "
            "your shell, then re-run `make verify-llm`."
        )
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="commander-verify-llm-"))
    db_path = tmp_dir / "verify.db"
    workspace_root = tmp_dir / "workspaces"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        secrets = DBSecretsProvider(session_factory)
        event_bus = InProcessEventBus(session_factory)
        agent_runtime = DBAgentRuntime(session_factory, event_bus)
        workspace_manager = LocalGitWorkspaceManager(str(workspace_root))
        sandbox_runner = DockerSandbox(settings.commander_sandbox_image)
        workflow_engine = CommanderWorkflowEngine(
            session_factory, event_bus, agent_runtime, secrets, workspace_manager, sandbox_runner
        )

        print("Founding a throwaway company against the real Anthropic API...")
        project = await projects_service.create_project(
            session_factory, event_bus, agent_runtime, name="Real-LLM Verification", provider="anthropic"
        )

        task = await tasks_service.create_task(
            session_factory,
            event_bus,
            project.id,
            "Write a welcome note",
            "Draft a short, friendly one-paragraph welcome message for new users of our product.",
            "low",
        )
        print(f"Mission '{task.title}' created ({task.id}); assigning to the Department...")
        await tasks_service.assign_task(session_factory, event_bus, agent_runtime, workflow_engine, task.id, None)

        final_state = await wait_for_state(
            session_factory, task.id, TaskState.PENDING_APPROVAL, TaskState.FAILED, timeout=_TIMEOUT_SECONDS
        )

        if final_state == TaskState.FAILED:
            events = await event_bus.recent(project.id, limit=50)
            failure = next((e for e in events if e.type == EventType.TASK_FAILED), None)
            reason = failure.reason if failure else "(no TASK_FAILED event found)"
            print(f"FAIL: mission ended in FAILED state. Error: {reason}")
            return 1

        approval = (await approvals_service.list_pending(session_factory, project.id))[0]
        verdict = parse_verdict(approval.raw_summary)
        cost = await costs_service.summary_for_task(session_factory, task.id)

        print("\n--- Real-LLM verification: PASS ---")
        print(f"  Reviewer verdict parsed: {verdict}")
        print(f"  Sections parsed: {sorted(approval.sections.keys()) or '(none)'}")
        print(f"  Real token cost for this mission: ${cost:.6f}")
        print(
            "\nRecord this outcome (verdict + cost) in docs/DECISIONS.md's Sprint 7 "
            "section per the mission brief."
        )
        return 0
    except RuntimeError as exc:
        # e.g. a rejected API key -- AnthropicProvider already turned this
        # into a plain-language message; surface it as-is, no traceback.
        print(f"FAIL: {exc}")
        return 1
    finally:
        await engine.dispose()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
