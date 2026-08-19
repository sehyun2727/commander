"""Sprint 19 §4.8: four load-smoke scenarios, plain asyncio, no framework
(no k6/JMeter/Locust, no new dependency). Runs entirely against a
throwaway SQLite DB and temp-dir git workspaces in-process -- this script
itself is the "temporary throwaway process" §4.8 allows in place of a
running `make dev` instance, wired the same way tests/conftest.py's
`Harness`/`api_client` fixtures are, so HTTP-layer scenarios (query-count
instrumentation) exercise the real FastAPI routes via
`httpx.ASGITransport` with zero real network/Postgres/Docker.

COMMANDER_PROVIDER is irrelevant here -- every Company this script creates
explicitly requests `provider="mock"`, matching §4.8's "with
COMMANDER_PROVIDER=mock" instruction without depending on the ambient
environment variable.

Usage:
  apps/api/.venv/Scripts/python.exe scripts/load_smoke.py
"""

from __future__ import annotations

import asyncio
import ctypes
import gc
import shutil
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

import dataclasses  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from sqlalchemy import event as sa_event  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_models import Base, MemoryRecordORM  # noqa: E402
from app.core.lifecycle.task_states import TaskState  # noqa: E402
from app.core.secrets import DBSecretsProvider  # noqa: E402
from app.deps import (  # noqa: E402
    get_agent_runtime,
    get_event_bus,
    get_sandbox_runner,
    get_secrets,
    get_session_factory,
    get_workflow_engine,
    get_workspace_manager,
)
from app.main import app  # noqa: E402
from app.modules.agent_harness.budget import HarnessBudget  # noqa: E402
from app.modules.agent_harness.context import ToolRunContext  # noqa: E402
from app.modules.agent_harness.handlers import dispatch_tool_call  # noqa: E402
from app.modules.agent_runtime import DBAgentRuntime  # noqa: E402
from app.modules.auth import service as auth_service  # noqa: E402
from app.modules.event_bus import InProcessEventBus  # noqa: E402
from app.modules.memory.schemas import RecallRequest  # noqa: E402
from app.modules.memory.service import recall  # noqa: E402
from app.modules.projects import service as projects_service  # noqa: E402
from app.modules.sandbox import FakeSandbox  # noqa: E402
from app.modules.skill_templates.registry import GENERALIST  # noqa: E402
from app.modules.tasks import service as tasks_service  # noqa: E402
from app.modules.workflow_engine import CommanderWorkflowEngine  # noqa: E402
from app.modules.workspace_manager import LocalGitWorkspaceManager  # noqa: E402
from app.templates.software_company import ENGINEER  # noqa: E402

# Narrative pacing sleeps are a production UX device with no load-smoke
# value -- see tests/conftest.py for the identical rationale/precedent.
settings.commander_pacing_enabled = False

WORKABLE_ROLE = dataclasses.replace(
    ENGINEER, tools=("list_repository", "read_file", "search_repository", "inspect_git", "apply_patch", "run_validation")
)
WORKABLE_TEMPLATE = dataclasses.replace(GENERALIST, capabilities=("repository_tools",))


def _rss_bytes() -> int:
    """Cross-platform process RSS/working-set, without adding a psutil
    dependency: `resource.ru_maxrss` on POSIX (KB on Linux, bytes on
    macOS), `GetProcessMemoryInfo` via ctypes on Windows -- this dev
    environment is Windows, the deployment target (docs/DEPLOYMENT.md) is
    Linux, so both paths matter."""
    if sys.platform == "win32":

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_uint32),
                ("PageFaultCount", ctypes.c_uint32),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        return counters.WorkingSetSize

    import resource

    ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ru_maxrss * 1024 if sys.platform.startswith("linux") else ru_maxrss


class Stack:
    """One throwaway DB + fully-wired backend stack, mirroring
    tests/conftest.py's `Harness`/`api_client` so this script never
    touches the dev database, dev workspaces, or a running server."""

    def __init__(self, tmp_dir: Path) -> None:
        self.tmp_dir = tmp_dir
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_dir / 'load_smoke.db'}", echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.secrets = DBSecretsProvider(self.session_factory)
        self.event_bus = InProcessEventBus(self.session_factory)
        self.agent_runtime = DBAgentRuntime(self.session_factory, self.event_bus)
        self.workspace_manager = LocalGitWorkspaceManager(str(tmp_dir / "workspaces"))
        self.sandbox_runner = FakeSandbox()
        self.workflow_engine = CommanderWorkflowEngine(
            self.session_factory, self.event_bus, self.agent_runtime, self.secrets,
            self.workspace_manager, self.sandbox_runner,
        )
        self.user = None

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.user = await auth_service.register(self.session_factory, "load-smoke@commander.local", "loadsmoke123", "Load Smoke")

    def override_app(self) -> None:
        app.dependency_overrides[get_session_factory] = lambda: self.session_factory
        app.dependency_overrides[get_event_bus] = lambda: self.event_bus
        app.dependency_overrides[get_agent_runtime] = lambda: self.agent_runtime
        app.dependency_overrides[get_workflow_engine] = lambda: self.workflow_engine
        app.dependency_overrides[get_secrets] = lambda: self.secrets
        app.dependency_overrides[get_workspace_manager] = lambda: self.workspace_manager
        app.dependency_overrides[get_sandbox_runner] = lambda: self.sandbox_runner

    async def dispose(self) -> None:
        app.dependency_overrides.clear()
        await self.engine.dispose()


async def _wait_for_state(stack: Stack, task_id: str, *states: TaskState, timeout: float = 60.0) -> TaskState:
    target = {s.value for s in states}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        task = await tasks_service.get_task(stack.session_factory, task_id)
        if task.state in target:
            return TaskState(task.state)
        await asyncio.sleep(0.05)
    raise TimeoutError(f"mission {task_id} never reached {target} within {timeout}s")


async def _run_one_mission(stack: Stack, project_id: str, title: str) -> float:
    start = time.monotonic()
    task = await tasks_service.create_task(
        stack.session_factory, stack.event_bus, project_id, title, "Write a short, friendly welcome note.", "low",
    )
    await tasks_service.assign_task(
        stack.session_factory, stack.event_bus, stack.agent_runtime, stack.workflow_engine, task.id, None,
    )
    state = await _wait_for_state(stack, task.id, TaskState.PENDING_APPROVAL, TaskState.FAILED)
    if state != TaskState.PENDING_APPROVAL:
        raise AssertionError(f"mission {task.id} ended in {state}, expected pending_approval")
    return time.monotonic() - start


# ---------------------------------------------------------------------------
# Scenario 1 -- 1 Company x 10 sequential Missions
# ---------------------------------------------------------------------------

async def scenario_1(stack: Stack) -> dict:
    print("\n[Scenario 1] 1 Company x 10 sequential Missions")
    project = await projects_service.create_project(
        stack.session_factory, stack.event_bus, stack.agent_runtime, name="Load Smoke Sequential", provider="mock",
        owner_id=stack.user.id,
    )
    gc.collect()
    rss_before = _rss_bytes()
    durations: list[float] = []
    for i in range(10):
        duration = await _run_one_mission(stack, project.id, f"Mission {i + 1}")
        durations.append(duration)
        print(f"  mission {i + 1}/10 completed in {duration:.3f}s")
    gc.collect()
    rss_after = _rss_bytes()
    rss_growth_mb = (rss_after - rss_before) / (1024 * 1024)

    ratio = durations[-1] / durations[0] if durations[0] > 0 else 0.0
    assert ratio <= 1.5, f"10th mission ({durations[-1]:.3f}s) is {ratio:.2f}x the 1st ({durations[0]:.3f}s); expected <=1.5x"
    assert rss_growth_mb < 100, f"RSS grew {rss_growth_mb:.1f} MB over 10 missions; expected <100 MB"

    print(f"  PASS -- 10/10 completed, wall-time ratio {ratio:.2f}x, RSS growth {rss_growth_mb:.1f} MB")
    return {
        "scenario": "1. Sequential (1 Co x 10 Missions)",
        "detail": f"10/10 completed, 1st={durations[0]:.3f}s, 10th={durations[-1]:.3f}s, ratio={ratio:.2f}x, RSS +{rss_growth_mb:.1f} MB",
        "pass": True,
    }


# ---------------------------------------------------------------------------
# Scenario 2 -- 3 Companies x 3 concurrent Missions each
# ---------------------------------------------------------------------------

async def _read_sse_stream(client: httpx.AsyncClient, project_id: str, received: list, ready: asyncio.Event) -> None:
    async with client.stream("GET", "/api/events/stream", params={"project_id": project_id}) as response:
        response.raise_for_status()
        ready.set()  # headers are in -- the connection is actually registered on the EventBus now
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                received.append(line.split(":", 1)[1].strip())


async def scenario_2(stack: Stack) -> dict:
    print("\n[Scenario 2] 3 Companies x 3 concurrent Missions each")
    stack.override_app()

    # `httpx.ASGITransport` (used by scenarios 1/3) runs the whole ASGI app
    # call to completion and buffers the entire response body in memory
    # before it hands back an `httpx.Response` at all (see
    # `handle_async_request` in httpx/_transports/asgi.py) -- it has no
    # concept of a genuinely concurrent, incremental stream. The realtime
    # SSE endpoint's response never terminates on its own (heartbeat loop
    # until client disconnect), so under ASGITransport this deadlocks
    # outright -- reproducible with even a single connection, before any
    # response headers are seen, regardless of app code (Sprint 19 §4.8
    # finding). A real `uvicorn` server on loopback gives every connection
    # its own genuine socket, exactly like the product's actual deployment,
    # so streaming and concurrency both work as they do in production.
    # `uvicorn` is already a runtime dependency of apps/api (it's what `make
    # dev` runs), so this isn't a new dependency for the load-smoke script.
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=30.0) as client:
            login = await client.post("/api/auth/login", json={"email": stack.user.email, "password": "loadsmoke123"})
            assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"

            projects = [
                await projects_service.create_project(
                    stack.session_factory, stack.event_bus, stack.agent_runtime, name=f"Load Smoke Co {i + 1}",
                    provider="mock", owner_id=stack.user.id,
                )
                for i in range(3)
            ]

            received: dict[str, list] = {p.id: [] for p in projects}
            ready_events = [asyncio.Event() for _ in projects]
            stream_tasks = [
                asyncio.create_task(_read_sse_stream(client, p.id, received[p.id], ready_events[i]))
                for i, p in enumerate(projects)
            ]
            # Wait for every SSE connection to actually be registered on the
            # EventBus (response headers received) before any Mission
            # starts -- a flat sleep() here was a race under concurrent
            # load (Sprint 19 §4.8 finding): a slow-to-schedule connection
            # could still be mid-handshake when its Company's missions
            # finished publishing.
            await asyncio.wait_for(asyncio.gather(*(e.wait() for e in ready_events)), timeout=10.0)

            async def _company_missions(project_id: str) -> list[TaskState]:
                results = []
                for i in range(3):
                    task = await tasks_service.create_task(
                        stack.session_factory, stack.event_bus, project_id, f"Concurrent mission {i + 1}",
                        "Write a short welcome note.", "low",
                    )
                    await tasks_service.assign_task(
                        stack.session_factory, stack.event_bus, stack.agent_runtime, stack.workflow_engine, task.id, None,
                    )
                    results.append((task.id, task))
                states = await asyncio.gather(
                    *(_wait_for_state(stack, tid, TaskState.PENDING_APPROVAL, TaskState.FAILED) for tid, _ in results)
                )
                return states

            all_states = await asyncio.gather(*(_company_missions(p.id) for p in projects))

            for task in stream_tasks:
                task.cancel()
            stream_results = await asyncio.gather(*stream_tasks, return_exceptions=True)
    finally:
        server.should_exit = True
        await asyncio.wait_for(server_task, timeout=10.0)

    stream_errors = [r for r in stream_results if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError)]
    assert not stream_errors, f"SSE stream(s) failed: {stream_errors}"

    for project, states in zip(projects, all_states):
        assert all(s == TaskState.PENDING_APPROVAL for s in states), f"company {project.id}: not all missions reached pending_approval: {states}"
        assert len(received[project.id]) > 0, f"company {project.id}: SSE stream received zero events during the run"

    print(f"  PASS -- 3 companies x 3 missions each reached pending_approval, no deadlock, all 3 SSE streams stayed connected")
    return {
        "scenario": "2. Concurrent (3 Co x 3 Missions)",
        "detail": "9/9 missions reached pending_approval, no deadlock, 3/3 SSE streams stayed connected throughout",
        "pass": True,
    }


# ---------------------------------------------------------------------------
# Scenario 3 -- hot-path query counts
# ---------------------------------------------------------------------------

async def _count_statements(stack: Stack, coro):
    async with stack.session_factory() as probe_session:
        sync_engine = probe_session.bind.sync_engine
    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa_event.listen(sync_engine, "before_cursor_execute", _capture)
    try:
        result = await coro
    finally:
        sa_event.remove(sync_engine, "before_cursor_execute", _capture)
    return result, statements


async def scenario_3(stack: Stack) -> dict:
    print("\n[Scenario 3] Hot-path query counts (workspace/overview, situation, harness dispatch)")
    stack.override_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        login = await client.post("/api/auth/login", json={"email": stack.user.email, "password": "loadsmoke123"})
        assert login.status_code == 200

        small = await projects_service.create_project(
            stack.session_factory, stack.event_bus, stack.agent_runtime, name="QC Small", provider="mock",
            owner_id=stack.user.id,
        )
        large = await projects_service.create_project(
            stack.session_factory, stack.event_bus, stack.agent_runtime, name="QC Large", provider="mock",
            owner_id=stack.user.id,
        )
        for i in range(5):
            await _run_one_mission(stack, large.id, f"Seed mission {i + 1}")

        overview_counts = {}
        situation_counts = {}
        for label, project in (("small", small), ("large", large)):
            _, statements = await _count_statements(
                stack, client.get(f"/api/projects/{project.id}/workspace/overview")
            )
            selects = [s for s in statements if s.strip().upper().startswith("SELECT")]
            overview_counts[label] = len(selects)

            _, statements = await _count_statements(stack, client.get(f"/api/projects/{project.id}/situation"))
            selects = [s for s in statements if s.strip().upper().startswith("SELECT")]
            situation_counts[label] = len(selects)

    assert overview_counts["small"] == overview_counts["large"], (
        f"workspace/overview query count scales with Mission count: small={overview_counts['small']}, large={overview_counts['large']}"
    )
    assert overview_counts["small"] <= 15, f"workspace/overview issued {overview_counts['small']} SELECTs, expected <=15"
    assert situation_counts["small"] == situation_counts["large"], (
        f"situation query count scales with Mission count: small={situation_counts['small']}, large={situation_counts['large']}"
    )
    assert situation_counts["small"] <= 15, f"situation issued {situation_counts['small']} SELECTs, expected <=15"

    # Harness dispatch: one read_file call should write exactly the audit
    # row (dispatch_tool_call never publishes an event for a pure read).
    harness_project = await projects_service.create_project(
        stack.session_factory, stack.event_bus, stack.agent_runtime, name="QC Harness", provider="mock",
        owner_id=stack.user.id,
    )
    await stack.workspace_manager.ensure_initialized(harness_project.id)
    await stack.workspace_manager.write_files(harness_project.id, "main", {"README.md": "hello\n"})
    await stack.workspace_manager.commit(harness_project.id, "main", "seed")
    branch_name = "mission/loadsmoke"
    await stack.workspace_manager.create_branch(harness_project.id, branch_name)

    context = ToolRunContext(
        project_id=harness_project.id,
        task_id="load-smoke-task",
        agent_id="load-smoke-agent",
        repo_root=stack.workspace_manager.repo_root(harness_project.id),
        branch_name=branch_name,
        role=WORKABLE_ROLE,
        skill_template=WORKABLE_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
        budget=HarnessBudget(stage="engineer"),
        branch_base_sha="0" * 40,
    )

    _, statements = await _count_statements(
        stack,
        dispatch_tool_call(
            context,
            workspace_manager=stack.workspace_manager,
            sandbox_runner=stack.sandbox_runner,
            session_factory=stack.session_factory,
            tool_name="read_file",
            call_id="load-smoke-call-1",
            raw_arguments={"path": "README.md"},
        ),
    )
    writes = [s for s in statements if s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert len(writes) <= 2, f"dispatch_tool_call issued {len(writes)} write statements for one read_file call, expected <=2"

    print(
        f"  PASS -- overview SELECTs constant ({overview_counts['small']}), situation SELECTs constant ({situation_counts['small']}), "
        f"harness dispatch wrote {len(writes)} row(s)"
    )
    return {
        "scenario": "3. Hot-path query counts",
        "detail": (
            f"workspace/overview: {overview_counts['small']} SELECTs (constant across 0 vs 5 missions); "
            f"situation: {situation_counts['small']} SELECTs (constant); harness dispatch: {len(writes)} write(s) per call"
        ),
        "pass": True,
    }


# ---------------------------------------------------------------------------
# Scenario 4 -- memory recall against 1,000 records
# ---------------------------------------------------------------------------

async def scenario_4(stack: Stack) -> dict:
    print("\n[Scenario 4] Memory recall against 1,000 records")
    project = await projects_service.create_project(
        stack.session_factory, stack.event_bus, stack.agent_runtime, name="Load Smoke Memory", provider="mock",
        owner_id=stack.user.id,
    )

    now = datetime.now(timezone.utc)
    rows = [
        MemoryRecordORM(
            project_id=project.id,
            category="failed_attempts" if i % 2 == 0 else "decisions",
            source_event_id=str(uuid.uuid4()),
            title=f"Record {i}",
            content_json={"preview": f"Record {i}"},
            tags=["auth", "session"] if i % 5 == 0 else ["billing"],
            keywords_text="login password reset" if i % 5 == 0 else "invoice",
            created_at=now - timedelta(days=i % 90),
        )
        for i in range(1000)
    ]
    async with stack.session_factory() as session:
        session.add_all(rows)
        await session.commit()

    # Fresh, uncached connection: dispose the pooled engine/connection this
    # script has been using, then reconnect to the same SQLite file, so the
    # timed recall() below cannot benefit from a warm connection/plan cache.
    await stack.engine.dispose()
    fresh_engine = create_async_engine(f"sqlite+aiosqlite:///{stack.tmp_dir / 'load_smoke.db'}", echo=False)
    fresh_session_factory = async_sessionmaker(fresh_engine, expire_on_commit=False)

    try:
        start = time.monotonic()
        results = await recall(fresh_session_factory, project.id, RecallRequest(tags=["auth", "session"], keywords=["login"]))
        elapsed_ms = (time.monotonic() - start) * 1000
    finally:
        await fresh_engine.dispose()

    # Restore stack.engine/session_factory for any later scenario code (none
    # currently runs after scenario 4, but keep Stack internally consistent).
    stack.engine = create_async_engine(f"sqlite+aiosqlite:///{stack.tmp_dir / 'load_smoke.db'}", echo=False)
    stack.session_factory = async_sessionmaker(stack.engine, expire_on_commit=False)

    assert len(results) > 0, "recall() returned zero results against 1,000 seeded records"
    assert elapsed_ms < 200, f"recall() took {elapsed_ms:.1f}ms against 1,000 records; expected <200ms"

    print(f"  PASS -- recall() over 1,000 records returned {len(results)} result(s) in {elapsed_ms:.1f}ms")
    return {
        "scenario": "4. Memory recall (1,000 records)",
        "detail": f"recall() returned {len(results)} result(s) in {elapsed_ms:.1f}ms (fresh connection, <200ms budget)",
        "pass": True,
    }


async def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="commander-load-smoke-"))
    stack = Stack(tmp_dir)
    results = []
    failed = False
    try:
        await stack.init()

        for scenario in (scenario_1, scenario_2, scenario_3, scenario_4):
            try:
                results.append(await scenario(stack))
            except (AssertionError, TimeoutError, asyncio.TimeoutError) as exc:
                failed = True
                detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                results.append({"scenario": scenario.__name__, "detail": detail, "pass": False})
                print(f"  FAIL -- {detail}")

        print("\n--- Load smoke: evidence table ---\n")
        print("| Scenario | Result |")
        print("|---|---|")
        for r in results:
            mark = "PASS" if r["pass"] else "FAIL"
            print(f"| {r['scenario']} | {mark} -- {r['detail']} |")

        if failed:
            print("\nOne or more scenarios FAILED -- see detail above.")
            return 1
        print("\nAll four load-smoke scenarios PASS. Record this table in the Sprint 19 report and CHANGELOG.md.")
        return 0
    finally:
        await stack.dispose()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
