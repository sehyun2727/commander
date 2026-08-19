"""Sprint 18 Phase 2 -- `memory.service.recall` ranking, server-enforced
bounds, and project scoping (sprint-18.md §4.9/§4.10/§4.11). Projection
itself is Phase 1 territory (test_memory_projection.py); planning
integration is covered in test_planning_orchestrator.py."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.db_models import MemoryRecordORM
from app.modules.memory.registry import MAX_RECALL_LIMIT
from app.modules.memory.schemas import RecallRequest
from app.modules.memory.service import recall
from app.modules.projects.service import create_project

import pytest


async def _make_project(harness):
    return await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )


async def _make_record(harness, project_id: str, *, category="failed_attempts", tags=None, keywords_text="", age_days=0.0, title="A record") -> MemoryRecordORM:
    row = MemoryRecordORM(
        project_id=project_id,
        category=category,
        source_event_id=str(uuid.uuid4()),
        title=title,
        content_json={"preview": title},
        tags=tags or [],
        keywords_text=keywords_text,
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )
    async with harness.session_factory() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_recall_over_empty_memory_returns_empty_list(harness):
    project = await _make_project(harness)
    results = await recall(harness.session_factory, project.id, RecallRequest())
    assert results == []


@pytest.mark.asyncio
async def test_recall_ranks_by_tag_and_keyword_matches(harness):
    project = await _make_project(harness)
    strong = await _make_record(
        harness, project.id, tags=["auth", "session"], keywords_text="login password reset", title="Strong match"
    )
    weak = await _make_record(harness, project.id, tags=["auth"], keywords_text="", title="Weak match")
    none_match = await _make_record(harness, project.id, tags=["billing"], keywords_text="invoice", title="No match")

    results = await recall(
        harness.session_factory, project.id, RecallRequest(tags=["auth", "session"], keywords=["login"])
    )

    ids = [r.id for r in results]
    assert strong.id in ids
    assert weak.id in ids
    assert none_match.id not in ids
    assert ids.index(strong.id) < ids.index(weak.id)


@pytest.mark.asyncio
async def test_recall_with_no_tags_or_keywords_ranks_by_recency_only(harness):
    project = await _make_project(harness)
    older = await _make_record(harness, project.id, age_days=10, title="Older")
    newer = await _make_record(harness, project.id, age_days=1, title="Newer")

    results = await recall(harness.session_factory, project.id, RecallRequest())

    ids = [r.id for r in results]
    assert ids.index(newer.id) < ids.index(older.id)


@pytest.mark.asyncio
async def test_recall_ties_break_on_created_at_then_id(harness):
    project = await _make_project(harness)
    now = datetime.now(timezone.utc)
    first = MemoryRecordORM(
        project_id=project.id,
        category="failed_attempts",
        source_event_id=str(uuid.uuid4()),
        title="Tie A",
        content_json={},
        tags=[],
        keywords_text="",
        created_at=now,
        id="aaaa-tie",
    )
    second = MemoryRecordORM(
        project_id=project.id,
        category="failed_attempts",
        source_event_id=str(uuid.uuid4()),
        title="Tie B",
        content_json={},
        tags=[],
        keywords_text="",
        created_at=now,
        id="bbbb-tie",
    )
    async with harness.session_factory() as session:
        session.add_all([second, first])  # inserted out of id order on purpose
        await session.commit()

    results = await recall(harness.session_factory, project.id, RecallRequest())

    ids = [r.id for r in results]
    assert ids.index("aaaa-tie") < ids.index("bbbb-tie")


@pytest.mark.asyncio
async def test_recall_limit_is_capped_server_side(harness):
    project = await _make_project(harness)
    for i in range(MAX_RECALL_LIMIT + 5):
        await _make_record(harness, project.id, title=f"Record {i}", age_days=float(i))

    results = await recall(harness.session_factory, project.id, RecallRequest(limit=1000))

    assert len(results) == MAX_RECALL_LIMIT


@pytest.mark.asyncio
async def test_recall_categories_none_searches_all_six(harness):
    project = await _make_project(harness)
    a = await _make_record(harness, project.id, category="ceo_approvals", title="Approval")
    b = await _make_record(harness, project.id, category="failed_attempts", title="Failure")

    results = await recall(harness.session_factory, project.id, RecallRequest(categories=None))

    ids = {r.id for r in results}
    assert a.id in ids
    assert b.id in ids


@pytest.mark.asyncio
async def test_recall_categories_empty_list_returns_no_results(harness):
    project = await _make_project(harness)
    await _make_record(harness, project.id, category="ceo_approvals", title="Approval")

    results = await recall(harness.session_factory, project.id, RecallRequest(categories=[]))

    assert results == []


@pytest.mark.asyncio
async def test_recall_categories_filters_to_requested_set(harness):
    project = await _make_project(harness)
    approval = await _make_record(harness, project.id, category="ceo_approvals", title="Approval")
    failure = await _make_record(harness, project.id, category="failed_attempts", title="Failure")

    results = await recall(harness.session_factory, project.id, RecallRequest(categories=["failed_attempts"]))

    ids = {r.id for r in results}
    assert failure.id in ids
    assert approval.id not in ids


@pytest.mark.asyncio
async def test_recall_since_days_excludes_older_records(harness):
    project = await _make_project(harness)
    recent = await _make_record(harness, project.id, age_days=1, title="Recent")
    ancient = await _make_record(harness, project.id, age_days=400, title="Ancient")

    results = await recall(harness.session_factory, project.id, RecallRequest(since_days=30))

    ids = {r.id for r in results}
    assert recent.id in ids
    assert ancient.id not in ids


@pytest.mark.asyncio
async def test_recall_malformed_request_types_are_coerced_not_raised(harness):
    project = await _make_project(harness)
    await _make_record(harness, project.id, tags=["auth"], title="Some record")

    # A PM turn's recall_request with wrong sub-field types must never raise
    # -- RecallRequest coerces them away to safe defaults (sprint-18.md §4.10).
    request = RecallRequest.model_validate(
        {"tags": "auth", "keywords": 123, "categories": "not-a-list", "since_days": "soon", "limit": "lots"}
    )
    results = await recall(harness.session_factory, project.id, request)

    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_recall_is_project_scoped(harness):
    project_a = await _make_project(harness)
    project_b = await _make_project(harness)
    await _make_record(harness, project_a.id, title="Belongs to A")
    await _make_record(harness, project_b.id, title="Belongs to B")

    results = await recall(harness.session_factory, project_a.id, RecallRequest())

    assert len(results) == 1
    assert results[0].title == "Belongs to A"
