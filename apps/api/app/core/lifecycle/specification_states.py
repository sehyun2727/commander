"""Project Specification lifecycle: states and allowed transitions.

Sprint 12 §4.6: one state machine covers both the PM<->CTO planning run
and the resulting Project Specification -- they are the same aggregate (a
Specification row exists from the moment the CEO submits a request,
before any version of its content has been drafted), so there is no
separate "planning run" state machine duplicating most of the same
states. `draft`/`planning`/`clarification_required` describe the
in-flight planning exchange; `ready_for_review` onward describe CEO
review of the produced content.
"""

from enum import Enum


class SpecificationStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    CLARIFICATION_REQUIRED = "clarification_required"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"


SPECIFICATION_TRANSITIONS: dict[SpecificationStatus, set[SpecificationStatus]] = {
    SpecificationStatus.DRAFT: {
        SpecificationStatus.PLANNING,
        SpecificationStatus.CANCELLED,
    },
    SpecificationStatus.PLANNING: {
        SpecificationStatus.CLARIFICATION_REQUIRED,
        SpecificationStatus.READY_FOR_REVIEW,
        SpecificationStatus.FAILED,
        SpecificationStatus.CANCELLED,
    },
    SpecificationStatus.CLARIFICATION_REQUIRED: {
        SpecificationStatus.PLANNING,
        SpecificationStatus.CANCELLED,
        SpecificationStatus.FAILED,
    },
    SpecificationStatus.READY_FOR_REVIEW: {
        SpecificationStatus.APPROVED,
        SpecificationStatus.REVISION_REQUESTED,
        SpecificationStatus.REJECTED,
        SpecificationStatus.CANCELLED,
    },
    SpecificationStatus.REVISION_REQUESTED: {
        SpecificationStatus.PLANNING,
        SpecificationStatus.CANCELLED,
        SpecificationStatus.FAILED,
    },
    SpecificationStatus.APPROVED: set(),
    SpecificationStatus.REJECTED: set(),
    SpecificationStatus.CANCELLED: set(),
    SpecificationStatus.FAILED: set(),
}

TERMINAL_SPECIFICATION_STATUSES: frozenset[SpecificationStatus] = frozenset(
    {
        SpecificationStatus.APPROVED,
        SpecificationStatus.REJECTED,
        SpecificationStatus.CANCELLED,
        SpecificationStatus.FAILED,
    }
)
