"""Sprint 13: public, typed CEO Workspace snapshot schemas.

Every field here is safe for the CEO to see (docs/prompts/sprint-13.md
§4.5): status/summary data and the vetted `EventORM.reason` narration
channel already used by Situation/Reports, never a raw provider payload,
hidden system prompt, or unrestricted profile. `schema_version` is a
plain integer bumped on any breaking response-shape change -- no general
version-negotiation framework (§5).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

SCHEMA_VERSION = 1

# Bounds documented here once, referenced by service.py and this sprint's
# report (§4.12: bounded lists, no unbounded history loads).
MAX_RECENT_MISSIONS = 10
MAX_ACTIVE_MISSIONS = 10
MAX_RECENT_ACTIVITY = 20
MAX_EMPLOYEES = 25


class ProjectSummary(BaseModel):
    id: str
    name: str
    provider: str
    archived: bool
    created_at: datetime


class LeadershipSlot(BaseModel):
    role_key: str
    title: str
    occupied: bool
    employee_id: str | None
    employee_name: str | None


class EmployeeCounts(BaseModel):
    total: int
    busy: int
    idle: int
    error: int


class EmployeeSummary(BaseModel):
    id: str
    name: str
    role_key: str
    state: str
    current_task_id: str | None


class OrganizationSummary(BaseModel):
    leadership: list[LeadershipSlot]
    counts: EmployeeCounts
    employees: list[EmployeeSummary]


class Focus(BaseModel):
    resource_type: str | None
    resource_id: str | None
    status: str | None


class PendingClarification(BaseModel):
    specification_id: str
    questions: list[str]


class PendingSpecificationReview(BaseModel):
    specification_id: str
    version: int


class PendingApprovalItem(BaseModel):
    approval_id: str
    task_id: str
    subject: str


class PendingFailure(BaseModel):
    resource_type: str
    resource_id: str
    reason: str | None


class PendingActions(BaseModel):
    clarification: PendingClarification | None = None
    specification_review: PendingSpecificationReview | None = None
    approval: PendingApprovalItem | None = None
    failure: PendingFailure | None = None


class NextAction(BaseModel):
    kind: str
    title: str
    explanation: str
    target_resource_type: str | None
    target_resource_id: str | None
    route: str | None
    urgency: str
    requires_ceo_input: bool


class PlanningSummary(BaseModel):
    active: bool
    specification_id: str | None
    status: str | None
    current_version: int | None
    turn_count: int | None
    unresolved_questions: int


class MissionSummaryItem(BaseModel):
    id: str
    title: str
    state: str
    priority: str
    specification_id: str | None
    created_at: datetime
    updated_at: datetime


class MissionSummary(BaseModel):
    active: list[MissionSummaryItem]
    recent: list[MissionSummaryItem]


class ActivityItem(BaseModel):
    id: str
    seq: int
    type: str
    kind: str
    actor_role: str
    actor_name: str
    reason: str | None
    created_at: datetime


class WorkspaceSnapshot(BaseModel):
    schema_version: int
    generated_at: datetime
    project: ProjectSummary
    organization: OrganizationSummary
    focus: Focus
    pending_actions: PendingActions
    next_action: NextAction
    planning: PlanningSummary
    missions: MissionSummary
    recent_activity: list[ActivityItem]
    event_cursor: int
