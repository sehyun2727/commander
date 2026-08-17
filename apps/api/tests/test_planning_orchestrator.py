"""Sprint 12 Phase 2: the PM<->CTO planning orchestrator (brief §9), exercised
against the mock provider's deterministic fixture markers (see
app/modules/provider_gateway/mock_provider.py) rather than a real LLM.
"""

from __future__ import annotations

import pytest

from app.core.db_models import ActiveSpecificationLockORM, AgentORM, SpecificationTurnORM
from app.core.errors import (
    ActivePlanningExistsError,
    CTOVacantError,
    MalformedProviderOutputError,
    PlanningTurnBudgetExhaustedError,
)
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
)


async def _make_project(harness):
    return await create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id
    )


async def _hire_cto(harness, project_id: str, name: str = "Ada") -> AgentORM:
    return await hire_employee(harness.session_factory, harness.event_bus, project_id, "mock", "cto", name)


def _orchestrator(harness) -> PlanningOrchestrator:
    return PlanningOrchestrator(harness.session_factory, harness.event_bus, harness.agent_runtime, harness.secrets)


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
