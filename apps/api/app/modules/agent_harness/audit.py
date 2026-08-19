"""Durable audit persistence for Agent Harness tool calls (Sprint 16 §4.9,
DECISIONS.md #233).

Every tool call -- successful, denied, or errored -- is recorded as one
`HarnessToolCallORM` row, independent of in-memory tool-loop state, so
Reviewer/CEO evidence and the security audit have a durable record.
`summarize_arguments` deliberately strips file content before persisting
(a 30-file `apply_patch` call could otherwise duplicate megabytes of
mission code into an audit-only table); only paths, counts, and
non-content metadata are kept.
"""

from __future__ import annotations

import uuid
from typing import Any

from ...core.db_models import HarnessToolCallORM

MAX_SUMMARY_ITEMS = 30

# Sprint 17 §4.12/§5, DECISIONS.md #239: loop-level (not per-tool-call)
# diagnostics reuse `HarnessToolCallORM` with a reserved `"_loop:"`
# tool_name prefix instead of a new table/column. Real tool keys are all
# registry-owned and start with a lowercase letter (never an underscore),
# so this prefix can never collide with a genuine tool call.
_LOOP_EVENT_ARGUMENTS_PASSTHROUGH = {"correction_interception", "correction_exhausted", "employee_surrendered"}


def summarize_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """A bounded, content-free summary of a tool call's arguments, safe to
    persist and safe to show a Reviewer/CEO without re-exposing full file
    bodies or search-matched content."""
    if tool_name == "apply_patch":
        files = arguments.get("files") or []
        return {
            "file_count": len(files),
            "paths": [entry.get("path") for entry in files[:MAX_SUMMARY_ITEMS] if isinstance(entry, dict)],
        }
    if tool_name in ("read_file", "list_repository", "search_repository"):
        summary = {key: value for key, value in arguments.items() if key != "content"}
        return summary
    if tool_name == "run_validation":
        return {"profile": arguments.get("profile")}
    if tool_name in ("inspect_git", "revert_last_patch"):
        return {}
    tool_kind = tool_name[len("_loop:") :] if tool_name.startswith("_loop:") else None
    if tool_kind in _LOOP_EVENT_ARGUMENTS_PASSTHROUGH:
        # Already a small, server-owned dict (`{attempt, max_attempts}` /
        # `{attempts}` / `{text_length}`) -- pass through as-is, nothing to
        # bound or strip.
        return arguments
    return {"keys": sorted(arguments.keys())[:MAX_SUMMARY_ITEMS]}


async def record_tool_call(
    session_factory,
    *,
    project_id: str,
    task_id: str,
    agent_id: str,
    call_id: str,
    tool_name: str,
    status: str,
    arguments: dict[str, Any],
    output_excerpt: str,
    error_detail: str | None,
    duration_seconds: float,
) -> None:
    row = HarnessToolCallORM(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        call_id=call_id,
        tool_name=tool_name,
        status=status,
        arguments_summary=summarize_arguments(tool_name, arguments),
        output_excerpt=output_excerpt,
        error_detail=error_detail,
        duration_seconds=duration_seconds,
    )
    async with session_factory() as session:
        session.add(row)
        await session.commit()


async def record_loop_event(
    session_factory,
    *,
    project_id: str,
    task_id: str,
    agent_id: str,
    kind: str,
    arguments_summary: dict[str, Any],
    output_excerpt: str = "",
) -> None:
    """Sprint 17 §4.12/§5, DECISIONS.md #239: write one orchestrator-owned
    diagnostic row for a loop-level event (`kind` is one of
    `"correction_interception"` / `"correction_exhausted"` /
    `"employee_surrendered"`) using the reserved `tool_name = "_loop:{kind}"`
    convention. `status = "recorded"` marks these as orchestrator
    diagnostics, distinct from a real handler outcome
    (`"success"`/`"denied"`/`"error"`)."""
    row = HarnessToolCallORM(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        call_id=str(uuid.uuid4()),
        tool_name=f"_loop:{kind}",
        status="recorded",
        arguments_summary=arguments_summary,
        output_excerpt=output_excerpt,
        error_detail=None,
        duration_seconds=0.0,
    )
    async with session_factory() as session:
        session.add(row)
        await session.commit()
