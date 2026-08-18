"""Sprint 13 Phase 1: pure/domain tests for the CEO Workspace next-action
policy (`app/modules/workspace_overview/next_action.py`). No database, no
event loop -- `derive()` is a pure function over `WorkspaceFacts`, so every
precedence tier and edge case is directly constructible and deterministic.
"""

from __future__ import annotations

from app.modules.workspace_overview.next_action import (
    ApprovalFacts,
    LeadershipFacts,
    SpecFacts,
    TaskFacts,
    WorkspaceFacts,
    derive,
)

PROJECT_ID = "proj-1"


def _facts(**overrides) -> WorkspaceFacts:
    base = dict(
        project_id=PROJECT_ID,
        latest_specification=None,
        pending_approval=None,
        failed_or_blocked_tasks=(),
        active_tasks=(),
        leadership=(),
        has_any_task=True,
    )
    base.update(overrides)
    return WorkspaceFacts(**base)


def _spec(status: str, **overrides) -> SpecFacts:
    base = dict(
        id="spec-1",
        status=status,
        current_version=1,
        turn_count=1,
        clarification_questions=(),
        has_execution_task=False,
    )
    base.update(overrides)
    return SpecFacts(**base)


def test_tier1_clarification_beats_everything_else():
    facts = _facts(
        latest_specification=_spec("clarification_required", clarification_questions=("What auth scheme?",)),
        pending_approval=ApprovalFacts(id="a1", task_id="t1", subject="Ship the API"),
        failed_or_blocked_tasks=(TaskFacts(id="t2", title="X", state="failed"),),
        leadership=(LeadershipFacts(role_key="cto", title="CTO", occupied=False),),
    )
    action, focus = derive(facts)
    assert action.kind == "answer_clarification"
    assert action.requires_ceo_input is True
    assert action.target_resource_type == "specification"
    assert action.target_resource_id == "spec-1"
    assert focus.resource_type == "specification" and focus.resource_id == "spec-1"


def test_tier2_ready_for_review_beats_approval_and_failure():
    facts = _facts(
        latest_specification=_spec("ready_for_review"),
        pending_approval=ApprovalFacts(id="a1", task_id="t1", subject="Ship the API"),
        failed_or_blocked_tasks=(TaskFacts(id="t2", title="X", state="failed"),),
    )
    action, _ = derive(facts)
    assert action.kind == "review_specification"


def test_tier4_pending_approval_beats_failure_and_progress():
    facts = _facts(
        pending_approval=ApprovalFacts(id="a1", task_id="t1", subject="Ship the API"),
        failed_or_blocked_tasks=(TaskFacts(id="t2", title="X", state="failed"),),
        active_tasks=(TaskFacts(id="t3", title="Y", state="in_progress"),),
    )
    action, focus = derive(facts)
    assert action.kind == "review_approval"
    assert action.requires_ceo_input is True
    assert focus.resource_type == "task" and focus.resource_id == "t1"


def test_tier5_specification_failure_surfaces_before_task_progress():
    facts = _facts(
        latest_specification=_spec("failed"),
        active_tasks=(TaskFacts(id="t3", title="Y", state="in_progress"),),
    )
    action, _ = derive(facts)
    assert action.kind == "resolve_planning_failure"


def test_tier5_task_failure_beats_progress_and_setup():
    facts = _facts(
        failed_or_blocked_tasks=(TaskFacts(id="t2", title="X", state="failed"),),
        active_tasks=(TaskFacts(id="t3", title="Y", state="in_progress"),),
        leadership=(LeadershipFacts(role_key="cto", title="CTO", occupied=False),),
    )
    action, focus = derive(facts)
    assert action.kind == "resolve_mission_failure"
    assert action.target_resource_id == "t2"
    assert focus.status == "failed"


def test_tier6_approved_spec_ready_to_execute():
    facts = _facts(latest_specification=_spec("approved", has_execution_task=False))
    action, _ = derive(facts)
    assert action.kind == "begin_execution"
    assert action.requires_ceo_input is True


def test_tier6_does_not_fire_once_execution_task_exists():
    facts = _facts(latest_specification=_spec("approved", has_execution_task=True))
    action, _ = derive(facts)
    assert action.kind != "begin_execution"


def test_tier7_planning_in_progress_does_not_require_ceo_input():
    facts = _facts(latest_specification=_spec("planning"))
    action, _ = derive(facts)
    assert action.kind == "monitor_planning"
    assert action.requires_ceo_input is False


def test_tier7_mission_in_progress_beats_setup():
    facts = _facts(
        active_tasks=(TaskFacts(id="t3", title="Y", state="in_progress"),),
        leadership=(LeadershipFacts(role_key="cto", title="CTO", occupied=False),),
    )
    action, focus = derive(facts)
    assert action.kind == "monitor_mission"
    assert action.requires_ceo_input is False
    assert focus.resource_id == "t3"


def test_tier8_vacant_leadership_surfaces_as_setup():
    facts = _facts(
        has_any_task=True,
        leadership=(
            LeadershipFacts(role_key="pm", title="PM", occupied=True),
            LeadershipFacts(role_key="cto", title="CTO", occupied=False),
        ),
    )
    action, focus = derive(facts)
    assert action.kind == "setup_leadership"
    assert action.target_resource_id == "cto"
    assert focus.resource_type == "role"


def test_tier9_start_mission_when_no_tasks_ever_existed():
    facts = _facts(has_any_task=False)
    action, focus = derive(facts)
    assert action.kind == "start_mission"
    assert action.requires_ceo_input is True
    assert focus.resource_id is None


def test_tier10_no_action_is_the_final_fallback():
    facts = _facts(has_any_task=True)
    action, focus = derive(facts)
    assert action.kind == "no_action"
    assert action.requires_ceo_input is False
    assert action.target_resource_id is None
    assert focus.resource_type is None


def test_missing_target_never_desyncs_focus_and_next_action():
    """Whenever next_action points at a resource, focus must describe the
    exact same resource (docs/prompts/sprint-13.md §4.6)."""
    scenarios = [
        _facts(latest_specification=_spec("clarification_required")),
        _facts(latest_specification=_spec("ready_for_review")),
        _facts(pending_approval=ApprovalFacts(id="a1", task_id="t1", subject="S")),
        _facts(failed_or_blocked_tasks=(TaskFacts(id="t2", title="X", state="blocked"),)),
        _facts(latest_specification=_spec("approved")),
        _facts(latest_specification=_spec("draft")),
        _facts(active_tasks=(TaskFacts(id="t3", title="Y", state="assigned"),)),
        _facts(leadership=(LeadershipFacts(role_key="cto", title="CTO", occupied=False),)),
        _facts(has_any_task=False),
        _facts(),
    ]
    for facts in scenarios:
        action, focus = derive(facts)
        assert focus.resource_id == action.target_resource_id
        assert focus.resource_type == action.target_resource_type


def test_deterministic_for_identical_input():
    facts = _facts(latest_specification=_spec("ready_for_review"))
    first = derive(facts)
    second = derive(facts)
    assert first[0] == second[0]
    assert first[1] == second[1]


def test_reserved_tier3_is_currently_unreachable():
    """docs/DECISIONS.md #218: revision_requested and changes_requested are
    not CEO-actionable in the shipped lifecycle -- they resolve to tier 7
    (in progress) or produce no next_action of their own, never a
    dedicated 'revision' action kind."""
    facts = _facts(latest_specification=_spec("revision_requested"))
    action, _ = derive(facts)
    assert action.kind != "revision_required"
    assert action.kind == "monitor_planning"
