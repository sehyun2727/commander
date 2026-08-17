"""API/domain schemas for the Sprint 12 Project Specification surface.

Response models expose exactly the data that is safe for the CEO to see
(§4.9): turn text is the PM/CTO's actual persisted analysis/review/draft
content, never a hidden system prompt, raw provider chain-of-thought, or
credential. Every response here is built from ORM rows with
`from_attributes`, never from an unchecked provider payload directly.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SpecificationStartRequest(BaseModel):
    request_text: str
    source_task_id: str | None = None


class SpecificationClarificationAnswerRequest(BaseModel):
    answers: list[str]


class SpecificationRevisionRequest(BaseModel):
    feedback: str


class SpecificationRejectRequest(BaseModel):
    reason: str | None = None


class SpecificationCancelRequest(BaseModel):
    reason: str | None = None


class SpecificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    request_text: str
    source_task_id: str | None
    pm_agent_id: str | None
    cto_agent_id: str | None
    current_version: int
    turn_count: int
    clarification_questions: list | None
    clarification_answers: list | None
    stop_reason: str | None
    decision_comment: str | None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None


class SpecificationVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    specification_id: str
    version: int
    title: str
    problem_statement: str
    goals: list
    non_goals: list
    requirements: list
    acceptance_criteria: list
    technical_approach: str
    architecture_components: list
    data_migration_impact: str
    security_considerations: str
    observability_requirements: str
    test_plan: str
    risks: list
    dependencies: list
    assumptions: list
    unresolved_questions: list
    implementation_stages: list
    created_at: datetime


class SpecificationTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    specification_id: str
    turn_index: int
    actor_role: str
    role_key: str | None
    agent_id: str | None
    kind: str
    text: str
    created_at: datetime
