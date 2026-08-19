"""Harness orchestrator: the bounded provider/tool loop for `harness ==
"tool_loop"` Roles (Sprint 16 §5/§7, DECISIONS.md #235).

This is the "AgentRuntime integration adapter" from §5's boundary list --
it is deliberately *not* a generic shell wrapper, not a WorkflowEngine
replacement, not a provider adapter, and not a self-correction engine
(§4.14): one bounded loop within one pipeline stage, nothing more.
`workflow_engine.engine` calls `run_tool_loop` once per produce stage and
treats its `ToolLoopResult`/exception the same way it already treats a
one-shot `_run_role` call plus `_land_code_changes`.

Every tool call is dispatched through Phase 2's `dispatch_tool_call`
(schema-validate -> authorize -> run -> bound -> audit) -- this module
never touches the workspace, the sandbox, or the DB directly. Provider
output is untrusted: `result.tool_calls` are schema-validated inside
`dispatch_tool_call`, never trusted as-is.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ...core.errors import (
    PatchConflictError,
    SelfCorrectionExhaustedError,
    ToolCallMalformedError,
    ToolDeniedError,
    ToolLoopExhaustedError,
    ToolPathViolationError,
)
from ...core.interfaces.provider_gateway import ProviderGateway
from ...core.interfaces.sandbox import SandboxRunner
from ...core.interfaces.workspace_manager import WorkspaceManager
from . import audit
from .context import LoopState, ToolRunContext
from .handlers import dispatch_tool_call
from .output import bound_output
from .registry import TOOLS_BY_KEY
from .schemas import TOOL_ARGUMENT_SCHEMAS

logger = logging.getLogger("commander.agent_harness.orchestrator")

# Rule #13: never retry forever. A denied call and a malformed/rejected
# call are tracked as separate streaks (denial is a permission fact that
# won't change mid-loop; malformed/rejected is more likely a one-off the
# model can self-correct from) but both are bounded.
MAX_DENIED_STREAK = 2
MAX_MALFORMED_STREAK = 3

# Sprint 17 §4.3, DECISIONS.md #239: bounds specifically "how many times
# the loop will refuse to accept a termination attempt while the most
# recent validation failed" -- a third, independent dimension from the
# tool-call-count/wall-time `HarnessBudget` and from the denied/malformed
# streaks above.
MAX_CORRECTION_ATTEMPTS = 3

_RETRIABLE_TOOL_ERRORS = (ToolCallMalformedError, ToolPathViolationError, PatchConflictError)

# Sprint 17 §4.5, DECISIONS.md #239: mirrors `parsing.parse_verdict`'s
# lenient convention for `**Verdict:**` -- tolerant of surrounding prose
# and case so provider formatting quirks never turn a genuine surrender
# into a false "still working" read.
_SURRENDER_MARKER_RE = re.compile(r"\*\*Unable to Complete:\*\*", flags=re.IGNORECASE)

# Sprint 17 §4.4: server-owned, code-level constant -- never provider-
# supplied, never echoes raw validation output back (the Employee already
# has that from the previous `run_validation` tool_result block).
_CORRECTIVE_REMINDER_TEMPLATE = (
    "Your most recent validation run failed. Before finishing, you must "
    "either fix the failure and re-run validation until it passes, or "
    "explicitly surrender by ending your final message with "
    "'**Unable to Complete:** <reason>'. You have {remaining} correction "
    "attempt(s) remaining after this one."
)


def _corrective_reminder(remaining_attempts: int) -> str:
    return _CORRECTIVE_REMINDER_TEMPLATE.format(remaining=remaining_attempts)


def tool_schemas_for(tool_keys: frozenset[str]) -> list[dict]:
    """Anthropic-shaped `{name, description, input_schema}` tool
    definitions for exactly the tools this Employee is permitted to call
    right now. Built fresh per loop from the immutable registry + pydantic
    schemas -- never cached, since permission can differ per Employee/
    stage/company."""
    schemas = []
    for key in sorted(tool_keys):
        tool = TOOLS_BY_KEY[key]
        schema_cls = TOOL_ARGUMENT_SCHEMAS[key]
        schemas.append(
            {
                "name": tool.key,
                "description": tool.description,
                "input_schema": schema_cls.model_json_schema(),
            }
        )
    return schemas


@dataclass(frozen=True)
class ToolLoopResult:
    final_text: str
    stop_reason: str
    iterations: int
    tool_call_count: int
    usage: dict[str, int]


def _ok_block(call_id: str, output_text: str) -> dict:
    return {"type": "tool_result", "tool_use_id": call_id, "content": output_text}


def _error_block(call_id: str, detail: str) -> dict:
    return {"type": "tool_result", "tool_use_id": call_id, "content": detail, "is_error": True}


async def run_tool_loop(
    *,
    context: ToolRunContext,
    gateway: ProviderGateway,
    workspace_manager: WorkspaceManager,
    sandbox_runner: SandboxRunner,
    session_factory,
    model_ref: str,
    system: str,
    initial_user_message: str,
    permitted_tools: frozenset[str],
    loop_state: LoopState,
    agent_override: str | None = None,
    on_self_correction_triggered: Callable[[], Awaitable[None]] | None = None,
) -> ToolLoopResult:
    """Run one bounded provider/tool loop and return its final completion.

    Stops on: a completion with no tool calls while the most recent
    validation did not fail (`stop_reason` carries whatever the provider
    reported), an explicit surrender marker in the terminating text
    (`stop_reason = "employee_surrendered"`, Sprint 17 §4.5), a
    `HarnessBudget` exhaustion (`BudgetExceededError` propagates to the
    caller -- the same path `workflow_engine._run_pipeline` already uses to
    block a Mission), too many consecutive denied/malformed tool calls
    (`ToolLoopExhaustedError`), or correction-attempt exhaustion
    (`SelfCorrectionExhaustedError`, Sprint 17 §4.3). A termination attempt
    while the most recent validation failed is never itself a termination
    -- it is intercepted and turned into a correction cycle (§4.16).
    `asyncio.CancelledError` is never caught here -- it propagates out of
    whichever `await` was in flight, exactly like every other stage in
    `workflow_engine` (Sprint 9's cancellation model), so a cancelled
    Mission can never produce a late success."""
    messages: list[dict] = [{"role": "user", "content": initial_user_message}]
    tools = tool_schemas_for(permitted_tools)
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    denied_streak = 0
    malformed_streak = 0
    seen_call_ids: set[str] = set()
    iteration = 0
    tool_call_count = 0

    while True:
        context.budget.check()
        iteration += 1
        result = await gateway.complete(
            model_ref, system, messages, tools=tools, agent_override=agent_override
        )
        total_usage["input_tokens"] += result.input_tokens
        total_usage["output_tokens"] += result.output_tokens

        if not result.tool_calls:
            surrendered = bool(_SURRENDER_MARKER_RE.search(result.text or ""))
            if surrendered:
                bounded_text, _ = bound_output(result.text or "")
                await audit.record_loop_event(
                    session_factory,
                    project_id=context.project_id,
                    task_id=context.task_id,
                    agent_id=context.agent_id,
                    kind="employee_surrendered",
                    arguments_summary={"text_length": len(result.text or "")},
                    output_excerpt=bounded_text,
                )
                return ToolLoopResult(
                    final_text=result.text,
                    stop_reason="employee_surrendered",
                    iterations=iteration,
                    tool_call_count=tool_call_count,
                    usage=total_usage,
                )

            if loop_state.last_validation_status != "failed":
                return ToolLoopResult(
                    final_text=result.text,
                    stop_reason=result.stop_reason,
                    iterations=iteration,
                    tool_call_count=tool_call_count,
                    usage=total_usage,
                )

            # §4.16: last validation failed and there is no surrender --
            # this termination attempt is intercepted, not accepted.
            if loop_state.correction_attempts >= MAX_CORRECTION_ATTEMPTS:
                await audit.record_loop_event(
                    session_factory,
                    project_id=context.project_id,
                    task_id=context.task_id,
                    agent_id=context.agent_id,
                    kind="correction_exhausted",
                    arguments_summary={"attempts": loop_state.correction_attempts},
                )
                raise SelfCorrectionExhaustedError(
                    f"{loop_state.correction_attempts} correction attempt(s) exhausted; "
                    "most recent validation still failed"
                )

            loop_state.correction_attempts += 1
            await audit.record_loop_event(
                session_factory,
                project_id=context.project_id,
                task_id=context.task_id,
                agent_id=context.agent_id,
                kind="correction_interception",
                arguments_summary={
                    "attempt": loop_state.correction_attempts,
                    "max_attempts": MAX_CORRECTION_ATTEMPTS,
                },
            )
            if not loop_state.first_correction_emitted:
                if on_self_correction_triggered is not None:
                    await on_self_correction_triggered()
                loop_state.first_correction_emitted = True

            remaining = MAX_CORRECTION_ATTEMPTS - loop_state.correction_attempts
            messages.append({"role": "user", "content": _corrective_reminder(remaining)})
            continue

        assistant_blocks: list[dict] = []
        if result.text:
            assistant_blocks.append({"type": "text", "text": result.text})
        for call in result.tool_calls:
            assistant_blocks.append(
                {"type": "tool_use", "id": call.call_id, "name": call.tool_name, "input": call.arguments}
            )
        messages.append({"role": "assistant", "content": assistant_blocks})

        tool_result_blocks: list[dict] = []
        for call in result.tool_calls:
            context.budget.check()
            # §4.8/§10 idempotency: a repeated call_id (a replayed or
            # duplicated provider turn) is never re-executed -- apply_patch
            # is mutating, so re-running it on a stale call_id could double
            # a write. Answer with a benign, non-error tool_result instead
            # of silently dropping it (the provider still needs a reply for
            # every tool_use block it sent).
            if call.call_id in seen_call_ids:
                tool_result_blocks.append(_ok_block(call.call_id, "duplicate call_id; already handled, ignored"))
                continue
            seen_call_ids.add(call.call_id)
            context.budget.record_tool_call()
            tool_call_count += 1
            try:
                output_text = await dispatch_tool_call(
                    context,
                    workspace_manager=workspace_manager,
                    sandbox_runner=sandbox_runner,
                    session_factory=session_factory,
                    tool_name=call.tool_name,
                    call_id=call.call_id,
                    raw_arguments=call.arguments,
                    loop_state=loop_state,
                )
            except ToolDeniedError as exc:
                denied_streak += 1
                malformed_streak = 0
                tool_result_blocks.append(_error_block(call.call_id, str(exc)))
                if denied_streak > MAX_DENIED_STREAK:
                    raise ToolLoopExhaustedError(
                        f"{denied_streak} consecutive denied tool calls (last: {call.tool_name!r})"
                    ) from exc
                continue
            except _RETRIABLE_TOOL_ERRORS as exc:
                malformed_streak += 1
                denied_streak = 0
                tool_result_blocks.append(_error_block(call.call_id, str(exc)))
                if malformed_streak > MAX_MALFORMED_STREAK:
                    raise ToolLoopExhaustedError(
                        f"{malformed_streak} consecutive malformed/rejected tool calls "
                        f"(last: {call.tool_name!r})"
                    ) from exc
                continue
            denied_streak = 0
            malformed_streak = 0
            if call.tool_name == "revert_last_patch":
                # Sprint 17 §7.2 item 8: this bookkeeping is orchestrator-
                # state, not handler-state -- the handler already performed
                # the actual git reset. Only reachable on a successful
                # dispatch, so `apply_patch_commit_history` is guaranteed
                # non-empty here (the handler denies an empty history).
                if loop_state.apply_patch_commit_history:
                    loop_state.apply_patch_commit_history.pop()
                loop_state.last_validation_status = None
            tool_result_blocks.append(_ok_block(call.call_id, output_text))

        messages.append({"role": "user", "content": tool_result_blocks})
