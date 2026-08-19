"""Threat/behavioral tests for the Agent Harness orchestrator's bounded
provider/tool loop (Sprint 16 §5/§7/§10 Integration, DECISIONS.md #235).

Exercises `run_tool_loop` against a scripted `FakeGateway` (never a real
provider) plus the real `LocalGitWorkspaceManager`/`FakeSandbox` from
`conftest.Harness`, so loop mechanics (streaks, budget, dedup,
cancellation) are tested independently of any specific provider's output
shape. Tool authorization/path/patch/command-level threats already have
dedicated coverage in test_agent_harness_{handlers,permissions,guards}.py
-- this file only covers what only exists once handlers are driven by a
real bounded loop.
"""

from __future__ import annotations

import asyncio
import dataclasses

import pytest
from sqlalchemy import select

from app.core.db_models import HarnessToolCallORM
from app.core.errors import (
    BudgetExceededError,
    SelfCorrectionExhaustedError,
    ToolLoopExhaustedError,
)
from app.core.interfaces.provider_gateway import CompletionResult, ProviderGateway, ToolCallData
from app.modules.agent_harness.budget import HarnessBudget
from app.modules.agent_harness.context import LoopState, ToolRunContext
from app.modules.agent_harness.orchestrator import MAX_CORRECTION_ATTEMPTS, run_tool_loop
from app.modules.projects import service as projects_service
from app.modules.sandbox import FakeSandbox
from app.modules.skill_templates.registry import GENERALIST
from app.templates.software_company import ENGINEER

WORKABLE_ROLE = dataclasses.replace(
    ENGINEER,
    tools=("list_repository", "read_file", "search_repository", "inspect_git", "apply_patch", "run_validation"),
)
WORKABLE_TEMPLATE = dataclasses.replace(GENERALIST, capabilities=("repository_tools",))
UNGRANTED_ROLE = dataclasses.replace(ENGINEER, tools=())
WORKABLE_ROLE_WITH_REVERT = dataclasses.replace(
    ENGINEER,
    tools=(
        "list_repository",
        "read_file",
        "search_repository",
        "inspect_git",
        "apply_patch",
        "run_validation",
        "revert_last_patch",
    ),
)


class FakeGateway(ProviderGateway):
    """Returns scripted `CompletionResult`s (or raises a scripted
    exception) one per `complete()` call, in order -- never a real
    provider, so loop mechanics are tested independently of any specific
    provider's response shape."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls = 0

    async def complete(self, model_ref, system, messages, **opts):
        self.calls += 1
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def stream(self, model_ref, system, messages, usage=None, **opts):
        raise NotImplementedError


async def _make_project(harness):
    return await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )


async def _seed_workspace(harness, project_id: str) -> str:
    await harness.workspace_manager.ensure_initialized(project_id)
    await harness.workspace_manager.write_files(project_id, "main", {"README.md": "hello\n"})
    await harness.workspace_manager.commit(project_id, "main", "seed")
    branch_name = "mission/aaaaaaaa"
    await harness.workspace_manager.create_branch(project_id, branch_name)
    return branch_name


def _context(harness, project, branch_name, *, role=WORKABLE_ROLE, skill_template=WORKABLE_TEMPLATE, budget=None, branch_base_sha=None) -> ToolRunContext:
    return ToolRunContext(
        project_id=project.id,
        task_id="task-1",
        agent_id="agent-1",
        repo_root=harness.workspace_manager.repo_root(project.id),
        branch_name=branch_name,
        role=role,
        skill_template=skill_template,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
        budget=budget or HarnessBudget(stage="engineer"),
        branch_base_sha=branch_base_sha or "0" * 40,
    )


def _tool_use(call_id: str, tool_name: str, arguments: dict, text: str = "") -> CompletionResult:
    return CompletionResult(
        text=text, model="mock", provider="mock",
        tool_calls=(ToolCallData(call_id, tool_name, arguments),),
        stop_reason="tool_use",
    )


def _final(text: str = "done") -> CompletionResult:
    return CompletionResult(text=text, model="mock", provider="mock", stop_reason="end_turn")


async def _run(harness, context, gateway, *, permitted_tools=None, loop_state=None, on_self_correction_triggered=None) -> object:
    return await run_tool_loop(
        context=context,
        gateway=gateway,
        workspace_manager=harness.workspace_manager,
        sandbox_runner=harness.sandbox_runner,
        session_factory=harness.session_factory,
        model_ref="mock",
        system="sys",
        initial_user_message="Mission: build",
        permitted_tools=permitted_tools if permitted_tools is not None else frozenset(WORKABLE_ROLE.tools),
        loop_state=loop_state if loop_state is not None else LoopState(),
        on_self_correction_triggered=on_self_correction_triggered,
    )


@pytest.mark.asyncio
async def test_deterministic_read_patch_validate_complete(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "read_file", {"path": "README.md"}),
            _tool_use("call-2", "apply_patch", {"files": [{"path": "src/new.py", "content": "x = 1\n"}]}),
            _tool_use("call-3", "run_validation", {"profile": "pytest"}),
            _final("**Change Summary:** did the thing"),
        ]
    )

    result = await _run(harness, context, gateway)

    assert result.final_text == "**Change Summary:** did the thing"
    assert result.stop_reason == "end_turn"
    assert result.tool_call_count == 3
    assert result.iterations == 4
    content = await harness.workspace_manager.read_file(project.id, "src/new.py", ref=branch_name)
    assert content == "x = 1\n"
    assert len(harness.sandbox_runner.calls) == 1


@pytest.mark.asyncio
async def test_denied_tool_path_exhausts_after_streak(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=UNGRANTED_ROLE)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "read_file", {"path": "README.md"}),
            _tool_use("call-2", "read_file", {"path": "README.md"}),
            _tool_use("call-3", "read_file", {"path": "README.md"}),
        ]
    )

    with pytest.raises(ToolLoopExhaustedError):
        await _run(harness, context, gateway, permitted_tools=frozenset({"read_file"}))

    # provider cannot self-grant: even though the schema was offered, the
    # server-side role/skill intersection (empty tools) denied every call.
    assert gateway.calls == 3


@pytest.mark.asyncio
async def test_denied_streak_resets_on_intervening_success(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    # WORKABLE_ROLE permits read_file but not run_validation is irrelevant
    # here -- use an unknown tool name to trigger denial ("unknown tool")
    # between two real successes so the streak never exceeds the bound.
    gateway = FakeGateway(
        [
            _tool_use("call-1", "read_file", {"path": "README.md"}),
            _tool_use("call-2", "delete_repository", {}),
            _tool_use("call-3", "read_file", {"path": "README.md"}),
            _tool_use("call-4", "delete_repository", {}),
            _final("done"),
        ]
    )

    result = await _run(harness, context, gateway)

    assert result.final_text == "done"
    assert result.tool_call_count == 4


@pytest.mark.asyncio
async def test_malformed_tool_call_exhausts_after_streak(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    bad_args = {"path": "README.md", "unexpected_extra_field": True}
    gateway = FakeGateway(
        [
            _tool_use("call-1", "read_file", bad_args),
            _tool_use("call-2", "read_file", bad_args),
            _tool_use("call-3", "read_file", bad_args),
            _tool_use("call-4", "read_file", bad_args),
        ]
    )

    with pytest.raises(ToolLoopExhaustedError):
        await _run(harness, context, gateway)

    assert gateway.calls == 4


@pytest.mark.asyncio
async def test_duplicate_call_id_is_not_reexecuted(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    gateway = FakeGateway(
        [
            _tool_use("dup-1", "read_file", {"path": "README.md"}),
            _tool_use("dup-1", "apply_patch", {"files": [{"path": "src/should_not_exist.py", "content": "x\n"}]}),
            _final("done"),
        ]
    )

    result = await _run(harness, context, gateway)

    assert result.final_text == "done"
    assert result.tool_call_count == 1  # the duplicate call_id was never dispatched
    entries = await harness.workspace_manager.list_tree(project.id, ref=branch_name)
    assert not any(entry.path == "src/should_not_exist.py" for entry in entries)


@pytest.mark.asyncio
async def test_tool_call_budget_exhaustion_blocks_further_calls(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    budget = HarnessBudget(stage="engineer", max_tool_calls=0)
    context = _context(harness, project, branch_name, budget=budget)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "read_file", {"path": "README.md"}),
            _final("done"),
        ]
    )

    with pytest.raises(BudgetExceededError) as excinfo:
        await _run(harness, context, gateway)

    assert excinfo.value.limit_kind == "tool_calls"
    assert gateway.calls == 1  # the exhaustion is caught before a second provider call


@pytest.mark.asyncio
async def test_wall_time_budget_exhaustion_blocks_before_any_call(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    budget = HarnessBudget(stage="engineer", max_seconds=-1)
    context = _context(harness, project, branch_name, budget=budget)
    gateway = FakeGateway([])

    with pytest.raises(BudgetExceededError) as excinfo:
        await _run(harness, context, gateway)

    assert excinfo.value.limit_kind == "seconds"
    assert gateway.calls == 0


@pytest.mark.asyncio
async def test_cancellation_propagates_uncaught(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    gateway = FakeGateway([asyncio.CancelledError()])

    with pytest.raises(asyncio.CancelledError):
        await _run(harness, context, gateway)


# ---------------------------------------------------------------------------
# Sprint 17 §4.16/§10 -- correction lifecycle (interception, exhaustion,
# surrender) and §10 rollback tool behavior.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_validation_termination_is_intercepted_then_surrender_accepted(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    sandbox = FakeSandbox(default_status="failed")
    gateway = FakeGateway(
        [
            _tool_use("call-1", "run_validation", {"profile": "pytest"}),
            _final("done"),  # termination attempt while failed -- intercepted
            _final("**Unable to Complete:** cannot get the check to pass"),
        ]
    )
    loop_state = LoopState()
    triggered = []

    async def _on_trigger() -> None:
        triggered.append(1)

    result = await run_tool_loop(
        context=context,
        gateway=gateway,
        workspace_manager=harness.workspace_manager,
        sandbox_runner=sandbox,
        session_factory=harness.session_factory,
        model_ref="mock",
        system="sys",
        initial_user_message="Mission: build",
        permitted_tools=frozenset(WORKABLE_ROLE.tools),
        loop_state=loop_state,
        on_self_correction_triggered=_on_trigger,
    )

    assert result.stop_reason == "employee_surrendered"
    assert loop_state.correction_attempts == 1
    assert triggered == [1]
    assert gateway.calls == 3


@pytest.mark.asyncio
async def test_correction_callback_fires_only_once_across_multiple_interceptions(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    sandbox = FakeSandbox(default_status="failed")
    gateway = FakeGateway(
        [
            _tool_use("call-1", "run_validation", {"profile": "pytest"}),
            _final("done"),
            _final("done"),
            _final("**Unable to Complete:** giving up"),
        ]
    )
    loop_state = LoopState()
    triggered = []

    async def _on_trigger() -> None:
        triggered.append(1)

    result = await run_tool_loop(
        context=context,
        gateway=gateway,
        workspace_manager=harness.workspace_manager,
        sandbox_runner=sandbox,
        session_factory=harness.session_factory,
        model_ref="mock",
        system="sys",
        initial_user_message="Mission: build",
        permitted_tools=frozenset(WORKABLE_ROLE.tools),
        loop_state=loop_state,
        on_self_correction_triggered=_on_trigger,
    )

    assert result.stop_reason == "employee_surrendered"
    assert loop_state.correction_attempts == 2
    assert len(triggered) == 1


@pytest.mark.asyncio
async def test_correction_exhaustion_raises_after_max_attempts(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    sandbox = FakeSandbox(default_status="failed")
    gateway = FakeGateway(
        [
            _tool_use("call-1", "run_validation", {"profile": "pytest"}),
            _final("done"),
            _final("done"),
            _final("done"),
            _final("done"),
        ]
    )
    loop_state = LoopState()

    with pytest.raises(SelfCorrectionExhaustedError):
        await run_tool_loop(
            context=context,
            gateway=gateway,
            workspace_manager=harness.workspace_manager,
            sandbox_runner=sandbox,
            session_factory=harness.session_factory,
            model_ref="mock",
            system="sys",
            initial_user_message="Mission: build",
            permitted_tools=frozenset(WORKABLE_ROLE.tools),
            loop_state=loop_state,
        )

    assert loop_state.correction_attempts == MAX_CORRECTION_ATTEMPTS
    assert gateway.calls == 5


@pytest.mark.asyncio
async def test_surrender_marker_is_accepted_without_prior_failure(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    gateway = FakeGateway([_final("**Unable to Complete:** the task is underspecified")])

    result = await _run(harness, context, gateway)

    assert result.stop_reason == "employee_surrendered"


@pytest.mark.asyncio
async def test_normal_termination_unaffected_when_no_validation_ever_ran(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    gateway = FakeGateway([_final("**Change Summary:** trivial doc edit")])
    loop_state = LoopState()

    result = await _run(harness, context, gateway, loop_state=loop_state)

    assert result.stop_reason == "end_turn"
    assert loop_state.correction_attempts == 0


@pytest.mark.asyncio
async def test_loop_events_recorded_as_synthetic_audit_rows(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)
    sandbox = FakeSandbox(default_status="failed")
    gateway = FakeGateway(
        [
            _tool_use("call-1", "run_validation", {"profile": "pytest"}),
            _final("done"),
            _final("**Unable to Complete:** giving up"),
        ]
    )
    loop_state = LoopState()

    await run_tool_loop(
        context=context,
        gateway=gateway,
        workspace_manager=harness.workspace_manager,
        sandbox_runner=sandbox,
        session_factory=harness.session_factory,
        model_ref="mock",
        system="sys",
        initial_user_message="Mission: build",
        permitted_tools=frozenset(WORKABLE_ROLE.tools),
        loop_state=loop_state,
    )

    async with harness.session_factory() as session:
        rows = (
            await session.execute(
                select(HarnessToolCallORM).where(HarnessToolCallORM.task_id == context.task_id)
            )
        ).scalars().all()

    loop_kinds = {row.tool_name for row in rows if row.tool_name.startswith("_loop:")}
    assert loop_kinds == {"_loop:correction_interception", "_loop:employee_surrendered"}
    assert all(row.status == "recorded" for row in rows if row.tool_name.startswith("_loop:"))


@pytest.mark.asyncio
async def test_revert_last_patch_denied_when_no_patch_history(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE_WITH_REVERT)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "revert_last_patch", {}),
            _final("done"),
        ]
    )

    result = await _run(harness, context, gateway, permitted_tools=frozenset(WORKABLE_ROLE_WITH_REVERT.tools))

    assert result.final_text == "done"
    assert result.tool_call_count == 1


@pytest.mark.asyncio
async def test_revert_last_patch_reverts_single_patch_to_branch_base(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    branch_base_sha = await harness.workspace_manager.head_sha(project.id, branch_name)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE_WITH_REVERT, branch_base_sha=branch_base_sha)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "apply_patch", {"files": [{"path": "src/new.py", "content": "x = 1\n"}]}),
            _tool_use("call-2", "revert_last_patch", {}),
            _final("done"),
        ]
    )

    result = await _run(harness, context, gateway, permitted_tools=frozenset(WORKABLE_ROLE_WITH_REVERT.tools))

    assert result.final_text == "done"
    entries = await harness.workspace_manager.list_tree(project.id, ref=branch_name)
    assert not any(entry.path == "src/new.py" for entry in entries)
    assert await harness.workspace_manager.head_sha(project.id, branch_name) == branch_base_sha


@pytest.mark.asyncio
async def test_revert_last_patch_reverts_second_patch_to_first(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    branch_base_sha = await harness.workspace_manager.head_sha(project.id, branch_name)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE_WITH_REVERT, branch_base_sha=branch_base_sha)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "apply_patch", {"files": [{"path": "src/a.py", "content": "a = 1\n"}]}),
            _tool_use("call-2", "apply_patch", {"files": [{"path": "src/b.py", "content": "b = 1\n"}]}),
            _tool_use("call-3", "revert_last_patch", {}),
            _final("done"),
        ]
    )

    result = await _run(harness, context, gateway, permitted_tools=frozenset(WORKABLE_ROLE_WITH_REVERT.tools))

    assert result.final_text == "done"
    entries = await harness.workspace_manager.list_tree(project.id, ref=branch_name)
    paths = {entry.path for entry in entries}
    assert "src/a.py" in paths
    assert "src/b.py" not in paths
    assert await harness.workspace_manager.head_sha(project.id, branch_name) != branch_base_sha


@pytest.mark.asyncio
async def test_revert_last_patch_ignores_noop_patch_history(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    branch_base_sha = await harness.workspace_manager.head_sha(project.id, branch_name)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE_WITH_REVERT, branch_base_sha=branch_base_sha)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "apply_patch", {"files": [{"path": "src/a.py", "content": "a = 1\n"}]}),
            # byte-identical resubmit -- write_files still reports bytes written but
            # commit() is a no-op, so this must never grow apply_patch_commit_history.
            _tool_use("call-2", "apply_patch", {"files": [{"path": "src/a.py", "content": "a = 1\n"}]}),
            _tool_use("call-3", "revert_last_patch", {}),
            _final("done"),
        ]
    )

    result = await _run(harness, context, gateway, permitted_tools=frozenset(WORKABLE_ROLE_WITH_REVERT.tools))

    assert result.final_text == "done"
    assert await harness.workspace_manager.head_sha(project.id, branch_name) == branch_base_sha


@pytest.mark.asyncio
async def test_revert_last_patch_clears_last_validation_status_and_allows_termination(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    branch_base_sha = await harness.workspace_manager.head_sha(project.id, branch_name)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE_WITH_REVERT, branch_base_sha=branch_base_sha)
    sandbox = FakeSandbox(default_status="failed")
    gateway = FakeGateway(
        [
            _tool_use("call-1", "apply_patch", {"files": [{"path": "src/a.py", "content": "a = 1\n"}]}),
            _tool_use("call-2", "run_validation", {"profile": "pytest"}),
            _tool_use("call-3", "revert_last_patch", {}),
            _final("done"),
        ]
    )
    loop_state = LoopState()

    result = await run_tool_loop(
        context=context,
        gateway=gateway,
        workspace_manager=harness.workspace_manager,
        sandbox_runner=sandbox,
        session_factory=harness.session_factory,
        model_ref="mock",
        system="sys",
        initial_user_message="Mission: build",
        permitted_tools=frozenset(WORKABLE_ROLE_WITH_REVERT.tools),
        loop_state=loop_state,
    )

    assert result.stop_reason == "end_turn"
    assert loop_state.last_validation_status is None
    assert loop_state.correction_attempts == 0


@pytest.mark.asyncio
async def test_revert_last_patch_denied_by_role_permission(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=UNGRANTED_ROLE)
    gateway = FakeGateway(
        [
            _tool_use("call-1", "revert_last_patch", {}),
            _tool_use("call-2", "revert_last_patch", {}),
            _tool_use("call-3", "revert_last_patch", {}),
        ]
    )

    with pytest.raises(ToolLoopExhaustedError):
        await _run(harness, context, gateway, permitted_tools=frozenset({"revert_last_patch"}))


@pytest.mark.asyncio
async def test_revert_last_patch_ancestry_violation_is_denied_not_destructive(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    # An unrelated/invalid sha as the rollback floor -- simulates a corrupted
    # or malicious target; revert_last_commit's ancestry check must refuse
    # rather than perform a destructive reset.
    context = _context(
        harness, project, branch_name, role=WORKABLE_ROLE_WITH_REVERT, branch_base_sha="f" * 40
    )
    gateway = FakeGateway(
        [
            _tool_use("call-1", "apply_patch", {"files": [{"path": "src/a.py", "content": "a = 1\n"}]}),
            _tool_use("call-2", "revert_last_patch", {}),
            _final("done"),
        ]
    )
    result = await _run(harness, context, gateway, permitted_tools=frozenset(WORKABLE_ROLE_WITH_REVERT.tools))

    assert result.final_text == "done"
    entries = await harness.workspace_manager.list_tree(project.id, ref=branch_name)
    # the apply_patch file is still present -- the revert was denied, not applied
    assert any(entry.path == "src/a.py" for entry in entries)
