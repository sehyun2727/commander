from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.modules.agent_harness.budget import HarnessBudget
from app.modules.agent_harness.context import ToolRunContext
from app.modules.skill_templates.registry import GENERALIST
from app.templates.software_company import ENGINEER


def _make_context(tmp_path: Path) -> ToolRunContext:
    return ToolRunContext(
        project_id="proj-1",
        task_id="task-1",
        repo_root=tmp_path,
        branch_name="mission/abcd1234",
        role=ENGINEER,
        skill_template=GENERALIST,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
        budget=HarnessBudget(stage="engineer"),
    )


def test_context_is_frozen(tmp_path):
    context = _make_context(tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.task_id = "other"  # type: ignore[misc]


def test_context_budget_still_mutates_through_frozen_context(tmp_path):
    context = _make_context(tmp_path)
    context.budget.record_tool_call()
    assert context.budget.tool_calls_made == 1
