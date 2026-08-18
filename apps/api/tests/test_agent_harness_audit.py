"""Unit tests for agent_harness/audit.py (Sprint 16 §4.9, DECISIONS.md
#233): summarize_arguments must never leak full file content into the
bounded, persisted summary, and record_tool_call must persist exactly one
row per call."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db_models import HarnessToolCallORM
from app.modules.agent_harness import audit


def test_summarize_apply_patch_strips_file_content():
    summary = audit.summarize_arguments(
        "apply_patch",
        {"files": [{"path": "a.py", "content": "x" * 10_000}, {"path": "b.py", "content": "y" * 10_000}]},
    )

    assert summary == {"file_count": 2, "paths": ["a.py", "b.py"]}
    assert "x" * 10_000 not in str(summary)


def test_summarize_read_file_keeps_path_only():
    assert audit.summarize_arguments("read_file", {"path": "src/app.py"}) == {"path": "src/app.py"}


def test_summarize_run_validation_keeps_profile_only():
    assert audit.summarize_arguments("run_validation", {"profile": "pytest"}) == {"profile": "pytest"}


def test_summarize_inspect_git_is_empty():
    assert audit.summarize_arguments("inspect_git", {}) == {}


def test_summarize_unknown_tool_keeps_only_sorted_keys():
    summary = audit.summarize_arguments("mystery_tool", {"b": 1, "a": 2})
    assert summary == {"keys": ["a", "b"]}


@pytest.mark.asyncio
async def test_record_tool_call_persists_one_row(harness):
    await audit.record_tool_call(
        harness.session_factory,
        project_id="proj-1",
        task_id="task-1",
        agent_id="agent-1",
        call_id="call-1",
        tool_name="read_file",
        status="success",
        arguments={"path": "a.py"},
        output_excerpt="content",
        error_detail=None,
        duration_seconds=0.05,
    )

    async with harness.session_factory() as session:
        rows = (await session.execute(select(HarnessToolCallORM))).scalars().all()

    assert len(rows) == 1
    assert rows[0].tool_name == "read_file"
    assert rows[0].status == "success"
    assert rows[0].arguments_summary == {"path": "a.py"}
    assert rows[0].output_excerpt == "content"
    assert rows[0].error_detail is None
