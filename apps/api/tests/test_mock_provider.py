from __future__ import annotations

import pytest

from app.modules.provider_gateway.mock_provider import MockProvider


@pytest.mark.asyncio
async def test_planner_produces_a_numbered_plan():
    result = await MockProvider().complete(
        "planner-default", system="you are a PM", messages=[], task_title="Add search bar", task_description="basic search"
    )
    assert result.provider == "mock"
    assert result.model == "planner-default"
    assert "1." in result.text


@pytest.mark.asyncio
async def test_builder_produces_a_deliverable():
    result = await MockProvider().complete(
        "builder-default", system="you are an Engineer", messages=[], task_title="Build login page", task_description="email/password"
    )
    assert result.text.startswith("## Deliverable:")
    assert "Build login page" in result.text


@pytest.mark.asyncio
async def test_reviewer_output_always_ends_in_a_parseable_verdict_line():
    for _ in range(20):
        result = await MockProvider().complete(
            "reviewer-default", system="you are a Reviewer", messages=[], task_title="Anything", task_description=""
        )
        assert result.text.startswith("## Audit:")
        last_line = result.text.strip().splitlines()[-1]
        assert last_line in ("**Verdict:** Approved", "**Verdict:** Changes requested")


@pytest.mark.asyncio
async def test_complete_fabricates_plausible_usage():
    result = await MockProvider().complete(
        "builder-default", system="you are an Engineer", messages=[], task_title="Build login page", task_description="email/password"
    )
    assert result.input_tokens > 0
    assert result.output_tokens > 0


@pytest.mark.asyncio
async def test_stream_yields_chunks_that_join_into_full_text_and_reports_usage():
    opts = {"task_title": "Build login page", "task_description": "email/password", "stream_delay": 0}
    usage: dict[str, int] = {}
    chunks = [
        chunk
        async for chunk in MockProvider().stream(
            "builder-default", system="you are an Engineer", messages=[], usage=usage, **opts
        )
    ]
    assert "".join(chunks).startswith("## Deliverable:")
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0
