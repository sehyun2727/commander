"""Sprint 12 Phase 2: the PM<->CTO planning orchestrator (brief §9), exercised
against the mock provider's deterministic fixture markers (see
app/modules/provider_gateway/mock_provider.py) rather than a real LLM.

Sprint 18 Phase 2 adds the `recall_request` planning integration tests near
the bottom of this file -- they monkeypatch `MockProvider.complete` directly
(the same pattern `test_malformed_provider_output_fails_after_bounded_retry`
already uses) for turn-by-turn control over the PM/CTO JSON, since the mock
provider's own deterministic fixture text has no `recall_request` scenario
until Phase 3's demo marker lands.
"""

from __future__ import annotations

import json

import pytest

from app.core.db_models import ActiveSpecificationLockORM, AgentORM, MemoryRecordORM, SpecificationTurnORM
from app.core.errors import (
    ActivePlanningExistsError,
    CTOVacantError,
    MalformedProviderOutputError,
    PlanningTurnBudgetExhaustedError,
)
from app.core.interfaces.provider_gateway import CompletionResult
from app.core.lifecycle.agent_states import AgentState
from app.core.lifecycle.specification_states import SpecificationStatus
from app.modules.agent_runtime.service import hire_employee
from app.modules.planning import service as planning_service
from app.modules.planning.orchestrator import PlanningOrchestrator
from app.modules.projects.service import create_project
from app.modules.provider_gateway.mock_provider import (
    BLOCKING_FEASIBILITY_MARKER,
    CTO_FOLLOWUP_MARKER,
    NEEDS_CLARIFICATION_MARKER,
    RECALL_DEMO_MARKER,
    MockProvider,
)


async def _make_project(harness):
    return await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )


async def _hire_cto(harness, project_id: str, name: str = "Ada") -> AgentORM:
    return await hire_employee(harness.session_factory, harness.event_bus, project_id, "mock", "cto", name)


def _orchestrator(harness) -> PlanningOrchestrator:
    return PlanningOrchestrator(harness.session_factory, harness.event_bus, harness.agent_runtime, harness.secrets)


async def _plant_memory_record(harness, project_id: str, *, category: str, tags: list[str], title: str) -> None:
    import uuid

    row = MemoryRecordORM(
        project_id=project_id,
        category=category,
        source_event_id=str(uuid.uuid4()),
        title=title,
        content_json={"preview": title},
        tags=tags,
        keywords_text=" ".join(tags),
    )
    async with harness.session_factory() as session:
        session.add(row)
        await session.commit()


_MOCK_SPEC_FIELDS = {
    "title": "Add auth support",
    "problem_statement": "Users cannot authenticate.",
    "goals": ["Add login"],
    "non_goals": [],
    "requirements": ["Support email/password login"],
    "acceptance_criteria": ["A user can log in"],
    "technical_approach": "Add a session-based auth flow.",
    "architecture_components": [],
    "data_migration_impact": "None.",
    "security_considerations": "Hash passwords.",
    "observability_requirements": "Log login attempts.",
    "test_plan": "Unit test the login flow.",
    "risks": [],
    "dependencies": [],
    "assumptions": [],
    "unresolved_questions": [],
    "implementation_stages": ["Build login form", "Wire session storage"],
}


@pytest.mark.asyncio
async def test_fast_agreement_path_reaches_ready_for_review(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")

    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value
    assert spec.current_version == 1
    versions = await planning_service.list_versions(harness.session_factory, spec.id)
    assert len(versions) == 1
    assert versions[0].title.startswith("Specification:")

    turns = await planning_service.list_turns(harness.session_factory, spec.id)
    kinds = [t.kind for t in turns]
    assert kinds == ["analysis", "review", "draft"]


@pytest.mark.asyncio
async def test_start_raises_when_cto_is_vacant(harness):
    project = await _make_project(harness)

    with pytest.raises(CTOVacantError):
        await _orchestrator(harness).start(project.id, "Add a health check endpoint")


@pytest.mark.asyncio
async def test_clarification_path_pauses_then_resumes_to_ready(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    orchestrator = _orchestrator(harness)

    spec = await orchestrator.start(project.id, f"{NEEDS_CLARIFICATION_MARKER}: build a thing")
    assert spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value
    assert spec.resume_stage == "pm_analysis"
    assert spec.clarification_questions

    resumed = await orchestrator.resume_after_clarification(spec.id, ["Success means it deploys cleanly."])
    assert resumed.status == SpecificationStatus.READY_FOR_REVIEW.value

    turns = await planning_service.list_turns(harness.session_factory, spec.id)
    assert any(t.actor_role == "ceo" and t.kind == "clarification_answer" for t in turns)


@pytest.mark.asyncio
async def test_blocking_feasibility_path_pauses_then_resumes_to_ready(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    orchestrator = _orchestrator(harness)

    spec = await orchestrator.start(project.id, f"{BLOCKING_FEASIBILITY_MARKER}: build a thing")
    assert spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value
    assert spec.resume_stage == "cto_review"

    resumed = await orchestrator.resume_after_clarification(spec.id, ["Use a smaller scope instead."])
    assert resumed.status == SpecificationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_cto_followup_path_reaches_ready_without_ceo_pause(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    spec = await _orchestrator(harness).start(project.id, f"{CTO_FOLLOWUP_MARKER}: build a thing")

    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value
    turns = await planning_service.list_turns(harness.session_factory, spec.id)
    kinds = [t.kind for t in turns]
    assert "clarification_request" in kinds
    assert "clarification_answer" not in [t.kind for t in turns if t.actor_role == "ceo"]
    assert kinds == ["analysis", "review", "clarification_request", "clarification_answer", "draft"]


@pytest.mark.asyncio
async def test_turn_budget_exhaustion_fails_the_specification(harness, monkeypatch):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    monkeypatch.setattr("app.modules.planning.orchestrator.MAX_PLANNING_TURNS", 2)

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")

    assert spec.status == SpecificationStatus.FAILED.value
    assert spec.stop_reason == "turn_limit_exceeded"


@pytest.mark.asyncio
async def test_turn_budget_exhausted_error_message_shape(harness):
    err = PlanningTurnBudgetExhaustedError("spec-1", 6)
    assert "spec-1" in str(err)
    assert "6" in str(err)


@pytest.mark.asyncio
async def test_malformed_provider_output_fails_after_bounded_retry(harness, monkeypatch):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    calls = {"n": 0}

    async def _broken_complete(*args, **kwargs):
        calls["n"] += 1
        from app.core.interfaces.provider_gateway import CompletionResult

        return CompletionResult(text="not json", model="x", provider="mock", input_tokens=1, output_tokens=1)

    from app.modules.provider_gateway.mock_provider import MockProvider

    monkeypatch.setattr(MockProvider, "complete", _broken_complete)

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")

    assert spec.status == SpecificationStatus.FAILED.value
    assert spec.stop_reason == "malformed_provider_output"
    assert calls["n"] == 2  # MAX_MALFORMED_ATTEMPTS


@pytest.mark.asyncio
async def test_failed_planning_releases_agents_to_idle_and_lock(harness, monkeypatch):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    monkeypatch.setattr("app.modules.planning.orchestrator.MAX_PLANNING_TURNS", 1)

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")
    assert spec.status == SpecificationStatus.FAILED.value

    async with harness.session_factory() as session:
        pm = await session.get(AgentORM, spec.pm_agent_id)
        cto = await session.get(AgentORM, spec.cto_agent_id)
        lock = await session.get(ActiveSpecificationLockORM, project.id)
    assert pm.state == AgentState.IDLE.value
    assert cto.state == AgentState.IDLE.value
    assert lock is None


@pytest.mark.asyncio
async def test_cancel_releases_lock_and_agents(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    orchestrator = _orchestrator(harness)

    spec = await orchestrator.start(project.id, f"{NEEDS_CLARIFICATION_MARKER}: build a thing")
    assert spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value

    cancelled = await orchestrator.cancel(spec.id, "CEO changed their mind")
    assert cancelled is True

    result = await planning_service.get_specification(harness.session_factory, spec.id)
    assert result.status == SpecificationStatus.CANCELLED.value

    async with harness.session_factory() as session:
        lock = await session.get(ActiveSpecificationLockORM, project.id)
        pm = await session.get(AgentORM, result.pm_agent_id)
        cto = await session.get(AgentORM, result.cto_agent_id)
    assert lock is None
    assert pm.state == AgentState.IDLE.value
    assert cto.state == AgentState.IDLE.value


@pytest.mark.asyncio
async def test_second_planning_run_rejected_while_one_is_active(harness, monkeypatch):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    # Force the first run to pause (not complete/release its lock) so a
    # second concurrent start collides with the still-held active lock.
    spec = await _orchestrator(harness).start(project.id, f"{NEEDS_CLARIFICATION_MARKER}: first request")
    assert spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value

    with pytest.raises(ActivePlanningExistsError):
        await _orchestrator(harness).start(project.id, "second request")


@pytest.mark.asyncio
async def test_employee_model_ref_override_is_honored(harness):
    project = await _make_project(harness)
    from app.modules.model_registry import options_for_role

    cto_models = options_for_role("mock", "advisor")
    override_ref = next(m for m in cto_models if m != "advisor-default")
    cto = await hire_employee(
        harness.session_factory, harness.event_bus, project.id, "mock", "cto", "Ada", model_ref=override_ref
    )

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")
    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value
    assert cto.profile["model_ref"] == override_ref


@pytest.mark.asyncio
async def test_service_layer_start_planning_matches_orchestrator(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    spec = await planning_service.start_planning(
        harness.session_factory,
        harness.event_bus,
        harness.agent_runtime,
        harness.secrets,
        project.id,
        "Add a health check endpoint",
    )
    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_revision_round_produces_a_second_version(harness):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    orchestrator = _orchestrator(harness)

    spec = await orchestrator.start(project.id, "Add a health check endpoint")
    assert spec.current_version == 1

    revised = await orchestrator.submit_revision(spec.id, "Please add rate limiting too")
    assert revised.status == SpecificationStatus.READY_FOR_REVIEW.value
    assert revised.current_version == 2

    versions = await planning_service.list_versions(harness.session_factory, spec.id)
    assert len(versions) == 2


# --- Sprint 18 Phase 2: recall_request planning integration -----------------


@pytest.mark.asyncio
async def test_planning_run_without_recall_request_is_unchanged(harness):
    """Sprint 12/17 baseline behavior: a PM turn that never emits
    `recall_request` never triggers a recall, never publishes
    `memory.recalled` (sprint-18.md §7 item 6's counterpart -- "nothing
    happens" when the field is absent)."""
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")

    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value
    events = await harness.event_bus.recent(project.id, limit=50)
    assert not [e for e in events if e.type == "memory.recalled"]


@pytest.mark.asyncio
async def test_pm_recall_request_injects_message_and_publishes_event(harness, monkeypatch):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    await _plant_memory_record(
        harness, project.id, category="failed_attempts", tags=["auth"], title="Auth mission failed before"
    )

    calls: list[dict] = []

    async def _complete(self, model_ref, system, messages, **opts):
        calls.append({"kind": opts.get("planning_turn_kind"), "messages": messages})
        kind = opts.get("planning_turn_kind")
        if kind == "pm_analysis":
            text = json.dumps(
                {
                    "needs_clarification": False,
                    "analysis_summary": "Looks straightforward.",
                    "recall_request": {"categories": ["failed_attempts"], "tags": ["auth"]},
                }
            )
        elif kind == "cto_review":
            text = json.dumps({"blocking": False, "architecture_notes": "Fine.", "risks": []})
        elif kind == "pm_draft_or_followup":
            text = json.dumps(
                {"ready_to_draft": True, "follow_up_question": None, "specification": _MOCK_SPEC_FIELDS}
            )
        else:
            raise AssertionError(f"unexpected turn kind {kind!r}")
        return CompletionResult(text=text, model=model_ref, provider="mock", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(MockProvider, "complete", _complete)

    spec = await _orchestrator(harness).start(project.id, "Add auth support")

    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value

    cto_call = next(c for c in calls if c["kind"] == "cto_review")
    assert len(cto_call["messages"]) == 2
    assert "Memory recall results" in cto_call["messages"][0]["content"]
    assert "Auth mission failed before" in cto_call["messages"][0]["content"]

    draft_call = next(c for c in calls if c["kind"] == "pm_draft_or_followup")
    assert len(draft_call["messages"]) == 1  # consumed exactly once, not re-injected on later turns

    events = await harness.event_bus.recent(project.id, limit=50)
    recalled = [e for e in events if e.type == "memory.recalled"]
    assert len(recalled) == 1
    assert recalled[0].payload["match_count"] == 1
    assert recalled[0].payload["requested_categories"] == ["failed_attempts"]
    assert recalled[0].actor.role == "employee"


@pytest.mark.asyncio
async def test_pm_recall_request_with_zero_matches_publishes_event_without_message(harness, monkeypatch):
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    # No memory records planted -- the recall_request will match nothing.

    calls: list[dict] = []

    async def _complete(self, model_ref, system, messages, **opts):
        calls.append({"kind": opts.get("planning_turn_kind"), "messages": messages})
        kind = opts.get("planning_turn_kind")
        if kind == "pm_analysis":
            text = json.dumps(
                {
                    "needs_clarification": False,
                    "analysis_summary": "Looks straightforward.",
                    "recall_request": {"categories": ["failed_attempts"]},
                }
            )
        elif kind == "cto_review":
            text = json.dumps({"blocking": False, "architecture_notes": "Fine.", "risks": []})
        elif kind == "pm_draft_or_followup":
            text = json.dumps(
                {"ready_to_draft": True, "follow_up_question": None, "specification": _MOCK_SPEC_FIELDS}
            )
        else:
            raise AssertionError(f"unexpected turn kind {kind!r}")
        return CompletionResult(text=text, model=model_ref, provider="mock", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(MockProvider, "complete", _complete)

    spec = await _orchestrator(harness).start(project.id, "Add auth support")

    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value

    cto_call = next(c for c in calls if c["kind"] == "cto_review")
    assert len(cto_call["messages"]) == 1  # no empty "no results" block injected

    events = await harness.event_bus.recent(project.id, limit=50)
    recalled = [e for e in events if e.type == "memory.recalled"]
    assert len(recalled) == 1
    assert recalled[0].payload["match_count"] == 0
    assert recalled[0].payload["memory_ids"] == []


@pytest.mark.asyncio
async def test_cto_turn_with_recall_request_fails_validation(harness, monkeypatch):
    """Only PM turn kinds may carry `recall_request` (sprint-18.md §7) -- a
    CTO turn that includes it is malformed output and takes the existing
    bounded-retry-then-fail path, same as any other schema violation."""
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)

    calls = {"n": 0}

    async def _complete(self, model_ref, system, messages, **opts):
        kind = opts.get("planning_turn_kind")
        if kind == "pm_analysis":
            text = json.dumps({"needs_clarification": False, "analysis_summary": "Fine."})
        elif kind == "cto_review":
            calls["n"] += 1
            text = json.dumps(
                {
                    "blocking": False,
                    "architecture_notes": "Fine.",
                    "risks": [],
                    "recall_request": {"categories": ["failed_attempts"]},
                }
            )
        else:
            raise AssertionError(f"unexpected turn kind {kind!r}")
        return CompletionResult(text=text, model=model_ref, provider="mock", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(MockProvider, "complete", _complete)

    spec = await _orchestrator(harness).start(project.id, "Add a health check endpoint")

    assert spec.status == SpecificationStatus.FAILED.value
    assert spec.stop_reason == "malformed_provider_output"
    assert calls["n"] == 2  # MAX_MALFORMED_ATTEMPTS

    events = await harness.event_bus.recent(project.id, limit=50)
    assert not [e for e in events if e.type == "memory.recalled"]


# --- Sprint 18 Phase 3: RECALL_DEMO_MARKER end-to-end (real MockProvider) ---


@pytest.mark.asyncio
async def test_recall_demo_marker_runs_recall_end_to_end_via_real_mock_provider(harness, monkeypatch):
    """sprint-18.md §10 Phase 3 item 5: unlike the Phase 2 tests above (which
    monkeypatch MockProvider.complete entirely for turn-by-turn JSON
    control), this drives the *actual* deterministic mock_provider fixture
    text via RECALL_DEMO_MARKER -- the wrapper below only observes calls,
    it never replaces the real response."""
    project = await _make_project(harness)
    await _hire_cto(harness, project.id)
    await _plant_memory_record(
        harness, project.id, category="failed_attempts", tags=["auth"], title="Auth mission failed before"
    )

    calls: list[dict] = []
    original_complete = MockProvider.complete

    async def _observing_complete(self, model_ref, system, messages, **opts):
        calls.append({"kind": opts.get("planning_turn_kind"), "messages": messages})
        return await original_complete(self, model_ref, system, messages, **opts)

    monkeypatch.setattr(MockProvider, "complete", _observing_complete)

    spec = await _orchestrator(harness).start(project.id, f"{RECALL_DEMO_MARKER}: add auth support")

    assert spec.status == SpecificationStatus.READY_FOR_REVIEW.value

    cto_call = next(c for c in calls if c["kind"] == "cto_review")
    assert len(cto_call["messages"]) == 2
    assert "Memory recall results" in cto_call["messages"][0]["content"]
    assert "Auth mission failed before" in cto_call["messages"][0]["content"]

    draft_call = next(c for c in calls if c["kind"] == "pm_draft_or_followup")
    assert len(draft_call["messages"]) == 1  # consumed exactly once

    events = await harness.event_bus.recent(project.id, limit=50)
    recalled = [e for e in events if e.type == "memory.recalled"]
    assert len(recalled) == 1
    assert recalled[0].payload["match_count"] == 1
    assert recalled[0].payload["requested_categories"] == ["failed_attempts"]
