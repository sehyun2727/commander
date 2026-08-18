"""Threat/unit tests for the Agent Harness tool handlers and
dispatch_tool_call (Sprint 16 §4.6-4.11, DECISIONS.md #233).

Exercises handlers.py against the real LocalGitWorkspaceManager and
FakeSandbox (see conftest.Harness) rather than hand-rolled fakes, so path
confinement and diff/write behavior are the same code the pipeline itself
uses. RoleSpec/SkillTemplate are widened via dataclasses.replace() for
dispatch_tool_call's success-path tests. Since Phase 3 grants
ENGINEER.tools/GENERALIST.capabilities for real, the denial test uses an
explicitly empty role (UNGRANTED_ROLE) rather than relying on the stock
template being inert.
"""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import select

from app.core.db_models import HarnessToolCallORM
from app.core.errors import (
    PatchConflictError,
    ToolCallMalformedError,
    ToolDeniedError,
    ToolPathViolationError,
)
from app.modules.agent_harness.budget import HarnessBudget
from app.modules.agent_harness.context import ToolRunContext
from app.modules.agent_harness.handlers import (
    apply_patch,
    dispatch_tool_call,
    inspect_git,
    list_repository,
    read_file,
    run_validation,
    search_repository,
)
from app.modules.agent_harness.schemas import (
    ApplyPatchArgs,
    InspectGitArgs,
    ListRepositoryArgs,
    PatchFileEntry,
    ReadFileArgs,
    RunValidationArgs,
    SearchRepositoryArgs,
)
from app.modules.projects import service as projects_service
from app.modules.sandbox.settings import set_execution_enabled
from app.modules.skill_templates.registry import GENERALIST
from app.templates.software_company import ENGINEER

WORKABLE_ROLE = dataclasses.replace(
    ENGINEER, tools=("list_repository", "read_file", "search_repository", "inspect_git", "apply_patch", "run_validation")
)
WORKABLE_TEMPLATE = dataclasses.replace(GENERALIST, capabilities=("repository_tools",))
UNGRANTED_ROLE = dataclasses.replace(ENGINEER, tools=())


async def _make_project(harness):
    return await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock",
        owner_id=harness.user.id,
    )


async def _seed_workspace(harness, project_id: str) -> str:
    """Initializes the repo on main with two files, then branches off it
    for the mission -- mirrors what the pipeline does before an Engineer
    tool loop would ever start."""
    await harness.workspace_manager.ensure_initialized(project_id)
    await harness.workspace_manager.write_files(
        project_id, "main", {"README.md": "hello\n", "src/app.py": "print('hi')\n"}
    )
    await harness.workspace_manager.commit(project_id, "main", "seed")
    branch_name = "mission/aaaaaaaa"
    await harness.workspace_manager.create_branch(project_id, branch_name)
    return branch_name


def _context(harness, project, branch_name, *, role=ENGINEER, skill_template=GENERALIST, stage_kind="produce") -> ToolRunContext:
    return ToolRunContext(
        project_id=project.id,
        task_id="task-1",
        agent_id="agent-1",
        repo_root=harness.workspace_manager.repo_root(project.id),
        branch_name=branch_name,
        role=role,
        skill_template=skill_template,
        stage_kind=stage_kind,
        harness_enabled=True,
        workspace_ready=True,
        budget=HarnessBudget(stage="engineer"),
    )


@pytest.mark.asyncio
async def test_list_repository_returns_bounded_sorted_paths(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    result = await list_repository(context, harness.workspace_manager, ListRepositoryArgs(path=""))

    assert result.splitlines() == sorted(result.splitlines())
    assert "README.md" in result
    assert "src/app.py" in result


@pytest.mark.asyncio
async def test_list_repository_filters_by_prefix(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    result = await list_repository(context, harness.workspace_manager, ListRepositoryArgs(path="src"))

    assert result == "src/app.py"


@pytest.mark.asyncio
async def test_read_file_returns_content(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    result = await read_file(context, harness.workspace_manager, ReadFileArgs(path="src/app.py"))

    assert result == "print('hi')\n"


@pytest.mark.asyncio
async def test_read_file_rejects_path_escape(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    with pytest.raises(ToolPathViolationError):
        await read_file(context, harness.workspace_manager, ReadFileArgs(path="../outside.txt"))


@pytest.mark.asyncio
async def test_search_repository_finds_matching_lines(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    result = await search_repository(context, harness.workspace_manager, SearchRepositoryArgs(path="", pattern="hi"))

    assert "src/app.py:1:print('hi')" in result


@pytest.mark.asyncio
async def test_inspect_git_shows_branch_diff(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    await harness.workspace_manager.write_files(project.id, branch_name, {"src/app.py": "print('changed')\n"})
    await harness.workspace_manager.commit(project.id, branch_name, "change")
    context = _context(harness, project, branch_name)

    result = await inspect_git(context, harness.workspace_manager, InspectGitArgs())

    assert "changed" in result


@pytest.mark.asyncio
async def test_apply_patch_writes_all_files(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    result = await apply_patch(
        context,
        harness.workspace_manager,
        ApplyPatchArgs(files=[PatchFileEntry(path="src/new.py", content="x = 1\n", expected_content=None)]),
    )

    assert "wrote 1 file" in result
    content = await harness.workspace_manager.read_file(project.id, "src/new.py", ref=branch_name)
    assert content == "x = 1\n"


@pytest.mark.asyncio
async def test_apply_patch_rejects_whole_patch_on_any_path_violation(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    with pytest.raises(ToolPathViolationError):
        await apply_patch(
            context,
            harness.workspace_manager,
            ApplyPatchArgs(
                files=[
                    PatchFileEntry(path="src/good.py", content="ok\n", expected_content=None),
                    PatchFileEntry(path="../escape.py", content="bad\n", expected_content=None),
                ]
            ),
        )

    entries = await harness.workspace_manager.list_tree(project.id, ref=branch_name)
    assert not any(entry.path == "src/good.py" for entry in entries)


@pytest.mark.asyncio
async def test_apply_patch_detects_stale_expected_content(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    with pytest.raises(PatchConflictError):
        await apply_patch(
            context,
            harness.workspace_manager,
            ApplyPatchArgs(
                files=[PatchFileEntry(path="src/app.py", content="new\n", expected_content="stale content that never matched")]
            ),
        )


@pytest.mark.asyncio
async def test_run_validation_returns_disabled_message_when_execution_off(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    await set_execution_enabled(harness.session_factory, project.id, False)
    context = _context(harness, project, branch_name)

    result = await run_validation(
        context, harness.workspace_manager, harness.sandbox_runner, harness.session_factory, RunValidationArgs(profile="pytest")
    )

    assert "execution is disabled" in result


@pytest.mark.asyncio
async def test_run_validation_denies_unknown_profile(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    with pytest.raises(ToolDeniedError):
        await run_validation(
            context, harness.workspace_manager, harness.sandbox_runner, harness.session_factory,
            RunValidationArgs(profile="rm -rf /"),
        )


@pytest.mark.asyncio
async def test_run_validation_runs_named_profile_against_sandbox(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name)

    result = await run_validation(
        context, harness.workspace_manager, harness.sandbox_runner, harness.session_factory, RunValidationArgs(profile="pytest")
    )

    assert "[passed] pytest" in result
    assert len(harness.sandbox_runner.calls) == 1
    assert harness.sandbox_runner.calls[0][0] == "pytest"


@pytest.mark.asyncio
async def test_dispatch_tool_call_records_audit_row_on_success(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE, skill_template=WORKABLE_TEMPLATE)

    output = await dispatch_tool_call(
        context,
        workspace_manager=harness.workspace_manager,
        sandbox_runner=harness.sandbox_runner,
        session_factory=harness.session_factory,
        tool_name="read_file",
        call_id="call-1",
        raw_arguments={"path": "README.md"},
    )

    assert output == "hello\n"
    async with harness.session_factory() as session:
        rows = (await session.execute(select(HarnessToolCallORM))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].tool_name == "read_file"
    assert rows[0].output_excerpt == "hello\n"
    assert rows[0].arguments_summary == {"path": "README.md"}


@pytest.mark.asyncio
async def test_dispatch_tool_call_records_audit_row_on_denial(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=UNGRANTED_ROLE)

    with pytest.raises(ToolDeniedError):
        await dispatch_tool_call(
            context,
            workspace_manager=harness.workspace_manager,
            sandbox_runner=harness.sandbox_runner,
            session_factory=harness.session_factory,
            tool_name="read_file",
            call_id="call-2",
            raw_arguments={"path": "README.md"},
        )

    async with harness.session_factory() as session:
        rows = (await session.execute(select(HarnessToolCallORM))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "denied"


@pytest.mark.asyncio
async def test_dispatch_tool_call_records_audit_row_on_malformed_arguments(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE, skill_template=WORKABLE_TEMPLATE)

    with pytest.raises(ToolCallMalformedError):
        await dispatch_tool_call(
            context,
            workspace_manager=harness.workspace_manager,
            sandbox_runner=harness.sandbox_runner,
            session_factory=harness.session_factory,
            tool_name="read_file",
            call_id="call-3",
            raw_arguments={"path": "README.md", "unexpected_extra_field": True},
        )

    async with harness.session_factory() as session:
        rows = (await session.execute(select(HarnessToolCallORM))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "error"


@pytest.mark.asyncio
async def test_dispatch_tool_call_records_audit_row_on_unknown_tool(harness):
    project = await _make_project(harness)
    branch_name = await _seed_workspace(harness, project.id)
    context = _context(harness, project, branch_name, role=WORKABLE_ROLE, skill_template=WORKABLE_TEMPLATE)

    with pytest.raises(ToolDeniedError):
        await dispatch_tool_call(
            context,
            workspace_manager=harness.workspace_manager,
            sandbox_runner=harness.sandbox_runner,
            session_factory=harness.session_factory,
            tool_name="delete_repository",
            call_id="call-4",
            raw_arguments={},
        )

    async with harness.session_factory() as session:
        rows = (await session.execute(select(HarnessToolCallORM))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "error"
