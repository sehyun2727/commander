from __future__ import annotations

import pytest

from app.core.errors import BudgetExceededError
from app.modules.agent_harness.budget import HarnessBudget


def test_budget_allows_calls_within_bound():
    budget = HarnessBudget(stage="engineer", max_tool_calls=3, max_seconds=60)
    for _ in range(3):
        budget.record_tool_call()
        budget.check()  # must not raise


def test_budget_raises_once_tool_call_cap_exceeded():
    budget = HarnessBudget(stage="engineer", max_tool_calls=1, max_seconds=60)
    budget.record_tool_call()
    budget.record_tool_call()
    with pytest.raises(BudgetExceededError) as exc_info:
        budget.check()
    assert exc_info.value.limit_kind == "tool_calls"
    assert exc_info.value.stage == "engineer"


def test_budget_raises_once_wall_time_exceeded():
    budget = HarnessBudget(stage="engineer", max_tool_calls=1000, max_seconds=0)
    with pytest.raises(BudgetExceededError) as exc_info:
        budget.check()
    assert exc_info.value.limit_kind == "seconds"
