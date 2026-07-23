from __future__ import annotations

import pytest

from app.modules.costs import record_usage
from app.modules.costs.service import summary_for_project, summary_for_task
from app.modules.model_registry import cost_for


def test_cost_for_computes_from_the_price_table():
    # mock-builder-v1 is priced (3.00, 15.00) per million tokens.
    cost = cost_for("mock-builder-v1", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(18.00)


def test_cost_for_unknown_model_is_free_not_fatal():
    assert cost_for("some-future-model", input_tokens=1_000, output_tokens=1_000) == 0.0


@pytest.mark.asyncio
async def test_record_usage_and_summaries(harness):
    await record_usage(
        harness.session_factory,
        project_id="proj-1",
        task_id="task-1",
        agent_id="agent-pm",
        role="pm",
        provider="mock",
        model="mock-planner-v1",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    await record_usage(
        harness.session_factory,
        project_id="proj-1",
        task_id="task-1",
        agent_id="agent-eng",
        role="engineer",
        provider="mock",
        model="mock-builder-v1",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    month_total, by_agent = await summary_for_project(harness.session_factory, "proj-1")
    assert month_total == pytest.approx(1.50 + 18.00)
    assert dict(by_agent) == {"agent-pm": pytest.approx(1.50), "agent-eng": pytest.approx(18.00)}

    task_total = await summary_for_task(harness.session_factory, "task-1")
    assert task_total == pytest.approx(19.50)

    other_project_total, _ = await summary_for_project(harness.session_factory, "proj-2")
    assert other_project_total == 0.0
