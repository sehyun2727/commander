"""Safe tool handlers for the Agent Harness (Sprint 16 §4.6-4.11,
DECISIONS.md #233, #234).

Every handler receives a server-issued `ToolRunContext` (context.py) and
already-schema-validated arguments (schemas.py) -- never raw provider
text. Handlers call the existing `WorkspaceManager`/`SandboxRunner` ports
directly (the same ports `workflow_engine.engine` already uses for the
one-shot Engineer path); they never touch the filesystem or spawn a
process themselves, and no handler ever executes AI-supplied content
(Rule #9). `apply_patch` is the only mutating handler and pre-validates
every file via `guards.py` before writing any of them
(reject-whole-patch-on-any-violation), then commits immediately (not
deferred to tool-loop end, per DECISIONS.md #234) since every read-shaped
tool resolves through a committed git ref -- an uncommitted write would be
invisible to the Engineer's own next `read_file`/`inspect_git` call.

`dispatch_tool_call` is the single entry point Phase 3's harness
orchestrator uses: schema-validate -> authorize -> run the matching
handler -> bound the output -> persist an audit row. It never runs a
handler that hasn't just been authorized against the current context.
"""

from __future__ import annotations

import time

from pydantic import ValidationError

from ...core.errors import (
    PatchConflictError,
    ToolCallMalformedError,
    ToolDeniedError,
    ToolPathViolationError,
    WorkspaceConflictError,
)
from ...core.interfaces.sandbox import SandboxRunner
from ...core.interfaces.workspace_manager import WorkspaceManager
from ..sandbox import get_execution_enabled
from . import audit
from .context import LoopState, ToolRunContext
from .guards import guard_content, guard_path
from .output import bound_output
from .permissions import authorize_tool_call
from .profiles import resolve_validation_profile
from .schemas import (
    TOOL_ARGUMENT_SCHEMAS,
    ApplyPatchArgs,
    InspectGitArgs,
    ListRepositoryArgs,
    ReadFileArgs,
    RevertLastPatchArgs,
    RunValidationArgs,
    SearchRepositoryArgs,
)

MAX_SEARCH_RESULTS = 50
MAX_LIST_ENTRIES = 500


def _within_path(entry_path: str, prefix: str) -> bool:
    return not prefix or entry_path == prefix or entry_path.startswith(prefix + "/")


async def list_repository(context: ToolRunContext, workspace_manager: WorkspaceManager, args: ListRepositoryArgs) -> str:
    entries = await workspace_manager.list_tree(context.project_id, ref=context.branch_name)
    prefix = args.path.strip("/")
    names = sorted(entry.path for entry in entries if _within_path(entry.path, prefix))
    text, _ = bound_output("\n".join(names[:MAX_LIST_ENTRIES]))
    return text


async def read_file(context: ToolRunContext, workspace_manager: WorkspaceManager, args: ReadFileArgs) -> str:
    guard_path("read_file", context.repo_root, args.path)
    content = await workspace_manager.read_file(context.project_id, args.path, ref=context.branch_name)
    text, _ = bound_output(content)
    return text


async def search_repository(
    context: ToolRunContext, workspace_manager: WorkspaceManager, args: SearchRepositoryArgs
) -> str:
    entries = await workspace_manager.list_tree(context.project_id, ref=context.branch_name)
    prefix = args.path.strip("/")
    matches: list[str] = []
    for entry in sorted(e.path for e in entries if _within_path(e.path, prefix)):
        content = await workspace_manager.read_file(context.project_id, entry, ref=context.branch_name)
        if args.pattern not in content:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if args.pattern in line:
                matches.append(f"{entry}:{lineno}:{line.strip()}")
                if len(matches) >= MAX_SEARCH_RESULTS:
                    break
        if len(matches) >= MAX_SEARCH_RESULTS:
            break
    text, _ = bound_output("\n".join(matches))
    return text


async def inspect_git(context: ToolRunContext, workspace_manager: WorkspaceManager, args: InspectGitArgs) -> str:
    diff_text, truncated = await workspace_manager.diff(context.project_id, context.branch_name)
    text, _ = bound_output(diff_text)
    if truncated:
        text += "\n[diff truncated]"
    return text


async def apply_patch(
    context: ToolRunContext,
    workspace_manager: WorkspaceManager,
    args: ApplyPatchArgs,
    loop_state: LoopState | None = None,
) -> str:
    files: dict[str, str] = {}
    for entry in args.files:
        resolved_path = guard_path("apply_patch", context.repo_root, entry.path)
        guard_content("apply_patch", entry.content)
        if entry.expected_content is not None:
            current = resolved_path.read_text(encoding="utf-8", errors="ignore") if resolved_path.exists() else ""
            if current != entry.expected_content:
                raise PatchConflictError(entry.path)
        files[entry.path] = entry.content
    result = await workspace_manager.write_files(context.project_id, context.branch_name, files)
    if result.skipped:
        # Every entry was already pre-validated above; a skip here means the
        # manager's own validation disagreed (e.g. a filesystem race) -- treat
        # the whole patch as failed rather than silently landing a partial write.
        skipped_paths = ", ".join(path for path, _ in result.skipped)
        raise ToolPathViolationError("apply_patch", skipped_paths)
    if result.written:
        try:
            commit_result = await workspace_manager.commit(
                context.project_id, context.branch_name, f"apply_patch: {len(result.written)} file(s)"
            )
        except ValueError:
            # `write_files` reports a path as written whenever it wrote
            # bytes to disk, even if the content is byte-identical to what
            # was already committed on this branch (e.g. a retry attempt
            # that re-submits the same file) -- `commit()` then has
            # nothing staged. That's a no-op patch, not a real failure:
            # the Employee's requested content is already in place. Sprint
            # 17 §4.8: a no-op never grows `apply_patch_commit_history`.
            pass
        else:
            if loop_state is not None:
                loop_state.apply_patch_commit_history.append(commit_result.commit_sha)
    return f"wrote {len(result.written)} file(s): {', '.join(result.written)}"


async def run_validation(
    context: ToolRunContext,
    workspace_manager: WorkspaceManager,
    sandbox_runner: SandboxRunner,
    session_factory,
    args: RunValidationArgs,
    loop_state: LoopState | None = None,
) -> str:
    if not await get_execution_enabled(session_factory, context.project_id):
        return "execution is disabled for this company; validation did not run"
    profile = resolve_validation_profile(args.profile)
    if profile is None:
        raise ToolDeniedError("run_validation", f"unknown validation profile {args.profile!r}")
    entries = await workspace_manager.list_tree(context.project_id, ref=context.branch_name)
    files = {
        entry.path: await workspace_manager.read_file(context.project_id, entry.path, ref=context.branch_name)
        for entry in entries
    }
    result = await sandbox_runner.run_check(profile.name, files, list(profile.command))
    # Sprint 17 §7.2: the structural `CheckResult.status` -- never text
    # parsed from `result.output` -- is the only signal that ever updates
    # correction state.
    if loop_state is not None:
        loop_state.last_validation_status = result.status
    output, truncated = bound_output(result.output)
    summary = f"[{result.status}] {profile.name} ({result.duration_seconds:.1f}s)\n{output}"
    if truncated:
        summary += "\n[output truncated]"
    return summary


async def revert_last_patch(
    context: ToolRunContext,
    workspace_manager: WorkspaceManager,
    args: RevertLastPatchArgs,
    loop_state: LoopState | None,
) -> str:
    """Undo the most recent `apply_patch` commit this same tool loop
    produced (Sprint 17 §4.6-§4.7, DECISIONS.md #239). The target sha is
    always server-computed from `loop_state`/`context.branch_base_sha` --
    never provider-supplied (the schema has no fields). Post-success
    bookkeeping (popping the history entry, clearing
    `last_validation_status`) is deliberately left to the orchestrator
    (§7.2 item 8), which owns that state."""
    if loop_state is None or not loop_state.apply_patch_commit_history:
        raise ToolDeniedError("revert_last_patch", "no patch to revert")
    history = loop_state.apply_patch_commit_history
    target_sha = history[-2] if len(history) >= 2 else context.branch_base_sha
    try:
        await workspace_manager.revert_last_commit(context.project_id, context.branch_name, target_sha)
    except WorkspaceConflictError as exc:
        # `revert_last_commit`'s own ancestry check (§4.7 item 5) refused
        # before any reset ran -- translate to the tool-denial vocabulary
        # the rest of the harness uses rather than leaking a workspace-
        # manager-shaped exception through the tool boundary.
        raise ToolDeniedError("revert_last_patch", str(exc)) from exc
    return f"reverted 1 patch; branch now at {target_sha[:12]}"


async def dispatch_tool_call(
    context: ToolRunContext,
    *,
    workspace_manager: WorkspaceManager,
    sandbox_runner: SandboxRunner,
    session_factory,
    tool_name: str,
    call_id: str,
    raw_arguments: dict,
    loop_state: LoopState | None = None,
) -> str:
    """Validate, authorize, run, and audit exactly one tool call. Raises
    `ToolCallMalformedError`/`ToolDeniedError`/`ToolPathViolationError`/
    `PatchConflictError` on failure -- the caller (Phase 3's harness
    orchestrator) decides how each maps to a bounded retry or a blocked
    Mission. Every outcome, including failures, is recorded via
    `audit.record_tool_call` before the exception (if any) propagates.

    `loop_state` (Sprint 17 §5, DECISIONS.md #239) is only non-None during
    a tool-loop dispatch -- `apply_patch`/`run_validation`/
    `revert_last_patch` read and mutate it directly; every other consumer
    of this function passes `None` and those handlers behave exactly as
    they did in Sprint 16."""
    started = time.monotonic()
    status = "error"
    output_text = ""
    error_detail: str | None = None
    try:
        schema = TOOL_ARGUMENT_SCHEMAS.get(tool_name)
        if schema is None:
            raise ToolDeniedError(tool_name, "unknown tool")
        try:
            parsed = schema.model_validate(raw_arguments)
        except ValidationError as exc:
            raise ToolCallMalformedError(tool_name, 1, str(exc)) from exc

        try:
            authorize_tool_call(
                tool_name,
                role=context.role,
                skill_template=context.skill_template,
                stage_kind=context.stage_kind,
                harness_enabled=context.harness_enabled,
                workspace_ready=context.workspace_ready,
            )
        except ToolDeniedError:
            status = "denied"
            raise

        if tool_name == "list_repository":
            output_text = await list_repository(context, workspace_manager, parsed)
        elif tool_name == "read_file":
            output_text = await read_file(context, workspace_manager, parsed)
        elif tool_name == "search_repository":
            output_text = await search_repository(context, workspace_manager, parsed)
        elif tool_name == "inspect_git":
            output_text = await inspect_git(context, workspace_manager, parsed)
        elif tool_name == "apply_patch":
            output_text = await apply_patch(context, workspace_manager, parsed, loop_state)
        elif tool_name == "run_validation":
            output_text = await run_validation(
                context, workspace_manager, sandbox_runner, session_factory, parsed, loop_state
            )
        elif tool_name == "revert_last_patch":
            output_text = await revert_last_patch(context, workspace_manager, parsed, loop_state)
        else:  # pragma: no cover -- unreachable, schema lookup above already denies unknown tools
            raise ToolDeniedError(tool_name, "unknown tool")

        status = "success"
        return output_text
    except Exception as exc:
        if status != "denied":
            status = "error"
        error_detail = str(exc)
        raise
    finally:
        await audit.record_tool_call(
            session_factory,
            project_id=context.project_id,
            task_id=context.task_id,
            agent_id=context.agent_id,
            call_id=call_id,
            tool_name=tool_name,
            status=status,
            arguments=raw_arguments,
            output_excerpt=output_text,
            error_detail=error_detail,
            duration_seconds=time.monotonic() - started,
        )
