"""One-command real-LLM smoke test: drives a full Mission through a real
PM -> Engineer -> Reviewer pipeline and reports pass/fail.

Exercises exactly what Sprint 7 Phase 3 needs verified against real (not
mock) model output: the request actually reaches the provider, the
trailing **Verdict:** line still parses, a missing/invalid key surfaces as
a plain-language error instead of a traceback, and real token usage
becomes a real USD cost. Safe to run repeatedly -- everything happens in a
throwaway SQLite database and workspace directory, never touching the
project's own dev database or git history.

Usage:
  `make verify-llm` (Anthropic direct) or
  `make verify-llm-openrouter` (OpenRouter, Sprint 19), or directly:
  `apps/api/.venv/bin/python scripts/verify_real_llm.py --provider anthropic|openrouter`

Requires the matching API key (ANTHROPIC_API_KEY or OPENROUTER_API_KEY) to
be set in the repo-root .env or the environment -- exits early with a
plain-language message if it isn't.

Sprint 19 §4.5/§4.6 add two flags on top of the original single-mission
shape:

  --model <id>       In-process fixture (§4.5's own suggested approach):
                      overrides every logical ref in the resolved
                      provider's model_registry map to this exact model id
                      for the duration of this process only. Used to route
                      OpenRouter at "anthropic/claude-sonnet-4.5" for
                      release evidence without touching the DB-backed
                      per-role override machinery.

  --full-lifecycle    Walks the same order a first-time CEO would use
                      Commander (§4.5 design constraint #1): found Company
                      -> hire CTO -> start a Specification (PM<->CTO
                      planning) -> CEO approves -> begin-execution ->
                      Mission runs -> CEO Decision. Without this flag the
                      script keeps its original shortcut of creating and
                      assigning one Mission directly, which is sufficient
                      for the two release-evidence runs (§4.6) but not for
                      the free-tier full-E2E smoke test (§4.5).
"""

from __future__ import annotations

import argparse
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
from app.modules.agent_runtime.service import hire_employee  # noqa: E402
from app.modules.approvals import service as approvals_service  # noqa: E402
from app.modules.auth import service as auth_service  # noqa: E402
from app.modules.costs import service as costs_service  # noqa: E402
from app.modules.event_bus import InProcessEventBus  # noqa: E402
from app.modules.model_registry import registry as model_registry  # noqa: E402
from app.modules.planning import service as planning_service  # noqa: E402
from app.modules.projects import service as projects_service  # noqa: E402
from app.modules.sandbox import DockerSandbox  # noqa: E402
from app.modules.tasks import service as tasks_service  # noqa: E402
from app.modules.workflow_engine import CommanderWorkflowEngine  # noqa: E402
from app.modules.workflow_engine.parsing import parse_verdict  # noqa: E402
from app.modules.workspace_manager import LocalGitWorkspaceManager  # noqa: E402

_TIMEOUT_SECONDS = 120.0


def _override_model_registry(provider: str, model: str) -> None:
    """In-process fixture (§4.5): every logical ref for this provider now
    resolves to `model`. Never persisted -- the process exits right after
    this script's one mission, so there's nothing to restore."""
    model_registry.MODEL_REGISTRY[provider] = {
        ref: model for ref in model_registry.MODEL_REGISTRY[provider]
    }


async def wait_for_state(session_factory, task_id: str, *states: TaskState, timeout: float) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.5)
    raise TimeoutError(f"mission {task_id} never reached {target} within {timeout}s")


_PROVIDER_KEY_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY", lambda: settings.anthropic_api_key),
    "openrouter": ("OPENROUTER_API_KEY", lambda: settings.openrouter_api_key),
}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=sorted(_PROVIDER_KEY_ENV),
        default="anthropic",
        help="Which real provider to verify against (default: anthropic).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override every logical model ref for --provider to this exact model id "
        "for this process only (e.g. anthropic/claude-sonnet-4.5 when --provider openrouter).",
    )
    parser.add_argument(
        "--full-lifecycle",
        action="store_true",
        help="Walk found-Company -> hire-CTO -> Specification -> CEO-approve -> "
        "Mission -> CEO-Decision instead of the direct-Mission shortcut.",
    )
    args = parser.parse_args()

    env_name, read_key = _PROVIDER_KEY_ENV[args.provider]
    if not read_key():
        print(
            f"FAIL: no {env_name} configured.\n"
            f"Set it in the repo-root .env (see .env.example), or export it in "
            f"your shell, then re-run this script with --provider {args.provider}."
        )
        return 1

    if args.model:
        _override_model_registry(args.provider, args.model)
        print(f"Model registry override: every {args.provider} logical ref -> {args.model}")

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

        user = await auth_service.register(session_factory, "verify-llm@commander.local", "verifypassword123", "Verify LLM")

        print(f"Founding a throwaway company against the real {args.provider} API...")
        project = await projects_service.create_project(
            session_factory, event_bus, agent_runtime, name="Real-LLM Verification", provider=args.provider,
            owner_id=user.id,
        )

        if args.full_lifecycle:
            print("Hiring a CTO...")
            await hire_employee(session_factory, event_bus, project.id, args.provider, "cto", "Casey")

            print("Starting a Project Specification (PM<->CTO planning)...")
            spec = await planning_service.start_planning(
                session_factory,
                event_bus,
                agent_runtime,
                secrets,
                project.id,
                "Draft a short, friendly one-paragraph welcome message for new users of our product.",
            )
            print(f"Specification {spec.id} reached status={spec.status}")
            if spec.status not in ("ready_for_review",):
                print(f"FAIL: specification never reached ready_for_review (status={spec.status})")
                return 1

            spec = await planning_service.approve_specification(session_factory, event_bus, spec.id)
            print(f"CEO approved Specification v{spec.current_version}")

            task = await planning_service.begin_execution(
                session_factory, event_bus, agent_runtime, workflow_engine, spec.id
            )
            print(f"Mission '{task.title}' created ({task.id}) via begin-execution...")
        else:
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

        if args.full_lifecycle:
            print("CEO Decision: approving...")
            await approvals_service.decide(session_factory, workflow_engine, approval.id, "approve", "Verified via script")
            completed_state = await wait_for_state(
                session_factory, task.id, TaskState.COMPLETED, TaskState.FAILED, timeout=_TIMEOUT_SECONDS
            )
            print(f"Mission final state after CEO Decision: {completed_state.value}")

        cost = await costs_service.summary_for_task(session_factory, task.id)

        print("\n--- Real-LLM verification: PASS ---")
        print(f"  Reviewer verdict parsed: {verdict}")
        print(f"  Sections parsed: {sorted(approval.sections.keys()) or '(none)'}")
        print(f"  Real token cost for this mission: ${cost:.6f}")
        print(
            "\nRecord this outcome (provider, verdict, turn count, token spend, wall "
            "time) in docs/DECISIONS.md per the relevant sprint brief."
        )
        return 0
    except RuntimeError as exc:
        # e.g. a rejected API key -- AnthropicProvider/OpenRouterProvider
        # already turned this into a plain-language message; surface it
        # as-is, no traceback.
        print(f"FAIL: {exc}")
        return 1
    finally:
        await engine.dispose()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
