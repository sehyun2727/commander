from __future__ import annotations

import pytest

from app.core.lifecycle.specification_states import (
    SPECIFICATION_TRANSITIONS,
    TERMINAL_SPECIFICATION_STATUSES,
    SpecificationStatus,
)
from app.core.lifecycle.state_machine import InvalidTransition, transition


def test_draft_to_planning_is_allowed():
    assert (
        transition(SpecificationStatus.DRAFT, SpecificationStatus.PLANNING, SPECIFICATION_TRANSITIONS)
        == SpecificationStatus.PLANNING
    )


def test_draft_can_be_cancelled():
    assert (
        transition(SpecificationStatus.DRAFT, SpecificationStatus.CANCELLED, SPECIFICATION_TRANSITIONS)
        == SpecificationStatus.CANCELLED
    )


def test_draft_cannot_skip_straight_to_ready_for_review():
    with pytest.raises(InvalidTransition):
        transition(SpecificationStatus.DRAFT, SpecificationStatus.READY_FOR_REVIEW, SPECIFICATION_TRANSITIONS)


def test_planning_can_require_clarification():
    assert (
        transition(
            SpecificationStatus.PLANNING,
            SpecificationStatus.CLARIFICATION_REQUIRED,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.CLARIFICATION_REQUIRED
    )


def test_clarification_required_resumes_to_planning():
    assert (
        transition(
            SpecificationStatus.CLARIFICATION_REQUIRED,
            SpecificationStatus.PLANNING,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.PLANNING
    )


def test_planning_reaches_ready_for_review():
    assert (
        transition(
            SpecificationStatus.PLANNING,
            SpecificationStatus.READY_FOR_REVIEW,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.READY_FOR_REVIEW
    )


def test_ready_for_review_can_be_approved():
    assert (
        transition(
            SpecificationStatus.READY_FOR_REVIEW,
            SpecificationStatus.APPROVED,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.APPROVED
    )


def test_ready_for_review_can_request_revision():
    assert (
        transition(
            SpecificationStatus.READY_FOR_REVIEW,
            SpecificationStatus.REVISION_REQUESTED,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.REVISION_REQUESTED
    )


def test_revision_requested_returns_to_planning():
    assert (
        transition(
            SpecificationStatus.REVISION_REQUESTED,
            SpecificationStatus.PLANNING,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.PLANNING
    )


def test_ready_for_review_can_be_rejected():
    assert (
        transition(
            SpecificationStatus.READY_FOR_REVIEW,
            SpecificationStatus.REJECTED,
            SPECIFICATION_TRANSITIONS,
        )
        == SpecificationStatus.REJECTED
    )


@pytest.mark.parametrize("terminal", sorted(TERMINAL_SPECIFICATION_STATUSES, key=lambda s: s.value))
def test_terminal_statuses_have_no_outgoing_transitions(terminal):
    assert SPECIFICATION_TRANSITIONS[terminal] == set()


@pytest.mark.parametrize("terminal", sorted(TERMINAL_SPECIFICATION_STATUSES, key=lambda s: s.value))
def test_cannot_transition_out_of_a_terminal_status(terminal):
    with pytest.raises(InvalidTransition):
        transition(terminal, SpecificationStatus.PLANNING, SPECIFICATION_TRANSITIONS)


def test_every_status_has_a_transition_table_entry():
    assert set(SPECIFICATION_TRANSITIONS.keys()) == set(SpecificationStatus)


def test_approved_rejected_cancelled_failed_are_the_only_terminal_statuses():
    assert TERMINAL_SPECIFICATION_STATUSES == {
        SpecificationStatus.APPROVED,
        SpecificationStatus.REJECTED,
        SpecificationStatus.CANCELLED,
        SpecificationStatus.FAILED,
    }
