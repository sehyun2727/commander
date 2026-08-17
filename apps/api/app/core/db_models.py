"""SQLAlchemy ORM tables. Shared infrastructure (like core.events), so every
module may depend on it directly without violating "modules never import
each other" — the rule is about module-to-module coupling, not access to
the persistence floor.

Table names stay internal ("projects", "tasks", ...) per the terminology
rule: code/DB use engineering terms, only UI copy uses Commander terms.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    """A CEO account (Sprint 9, Rule #15). `password_hash` is NULL for
    non-local providers -- schema shape, not code, is what keeps a plaintext
    password column from ever existing."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_provider", "provider_subject", name="uq_users_auth_provider_subject"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_provider: Mapped[str] = mapped_column(String, default="local")
    provider_subject: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionORM(Base):
    """A logged-in session. `id` is the SHA-256 hash of the bearer token
    the CEO's browser holds in an HttpOnly cookie -- the raw token itself
    is never persisted, so a DB leak alone can't be replayed as a session
    (Sprint 9 §2.1)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String, default="mock")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentORM(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    role_key: Mapped[str] = mapped_column(String)  # RoleSpec.key, e.g. "pm" | "engineer" | "reviewer"
    name: Mapped[str] = mapped_column(String)
    profile: Mapped[dict] = mapped_column(JSON)  # AgentProfile.model_dump(mode="json")
    avatar_color: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="idle")
    current_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Sprint 10 Phase 3 §13: the resolver's "longest since assigned"
    # tie-break needs a per-Employee timestamp that no existing column
    # captures -- `current_task_id` is cleared on completion, so it can't
    # answer "when was this Employee last picked". Set by the resolver
    # itself each time it selects this Employee for a pipeline stage.
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RoleSingletonLockORM(Base):
    """Sprint 11 §4.10: the actual concurrency guarantee behind singleton
    Role enforcement. One row per (project_id, role_key) exists exactly
    while that singleton Role is occupied; the composite primary key --
    not a service-layer check-then-insert -- is what makes two
    simultaneous hiring transactions for the same singleton Role race-safe:
    both INSERT in the same transaction as their Employee row, the
    database allows exactly one to commit, and the loser's IntegrityError
    is converted to SingletonRoleViolation. Never written for
    singleton=False Roles, and never for a single company/role pair twice
    -- no employee-firing flow exists yet to delete a row once created."""

    __tablename__ = "role_singleton_locks"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    role_key: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String, default="normal")
    state: Mapped[str] = mapped_column(String, default="created")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    result_markdown: Mapped[str] = mapped_column(Text, default="")
    deliverable_type: Mapped[str] = mapped_column(String, default="code")
    branch_name: Mapped[str | None] = mapped_column(String, nullable=True)
    code_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    check_results: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Sprint 12 §4.7: set only when this Mission was created from an
    # approved Project Specification (the gated
    # `POST /specifications/{id}/begin-execution` path). NULL for every
    # legacy/manual Mission created through the pre-existing
    # `POST /projects/{id}/tasks` endpoint, which remains ungated -- see
    # docs/DECISIONS.md for the Sprint 12 backward-compatibility policy.
    #
    # tasks.specification_id -> specifications.id and
    # specifications.source_task_id -> tasks.id form a genuine FK cycle
    # between these two tables. use_alter+name lets SQLAlchemy resolve it
    # via ALTER TABLE ADD/DROP CONSTRAINT instead of failing to topologically
    # sort CREATE/DROP order (see docs/DECISIONS.md).
    specification_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "specifications.id",
            use_alter=True,
            name="fk_tasks_specification_id",
        ),
        nullable=True,
    )


class EventORM(Base):
    __tablename__ = "events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String, unique=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    actor_role: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String)
    actor_name: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ApprovalORM(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    subject: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reviewer identity captured at approval-creation time (avoids a join
    # to render "Reviewer avatar + name" on the DecisionCard).
    reviewer_agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Leniently parsed Problem/Recommendation/Risk/Impact -- any subset may
    # be present; never a hard contract (see workflow_engine.parsing).
    sections: Mapped[dict] = mapped_column(JSON, default=dict)
    # The Reviewer's full raw audit text, so the UI can always render
    # something meaningful even when every structured section is missing.
    raw_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostEntryORM(Base):
    """One row per provider call (per Employee turn). Derived telemetry,
    not a Timeline milestone — summarized on demand by the costs module
    rather than replayed as events."""

    __tablename__ = "cost_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    role: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ReportORM(Base):
    """CEO Daily Report — an on-demand snapshot of the prior 24h, not a
    scheduled/recurring artifact (no background scheduler in this
    sprint's scope, see docs/DECISIONS.md)."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary_markdown: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class SettingORM(Base):
    """Generic KV store for runtime-editable Company Settings (provider
    choice, secret overrides). Keyed per app instance, not per project —
    single local CEO, single company config surface for this sprint."""

    __tablename__ = "settings_kv"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class SpecificationORM(Base):
    """Sprint 12 §4.5/§4.6: one Project Specification aggregate covers both
    the PM<->CTO planning exchange and the resulting reviewable document --
    a row exists from the moment the CEO submits a request (status=draft),
    long before any `SpecificationVersionORM` content exists. `status`
    lifecycle lives in `core.lifecycle.specification_states`; every
    transition is validated through the shared `transition()` helper, the
    same pattern `TaskORM`/`AgentORM` already use.

    `current_version` is a pointer into `specification_versions`, never a
    column that itself holds content -- "request revision" always appends
    a new version row rather than mutating one in place (§4.8)."""

    __tablename__ = "specifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    request_text: Mapped[str] = mapped_column(Text)
    # Set only when planning was started from an existing Mission rather
    # than a fresh CEO request (Required Backend Capability #1). Optional:
    # the primary Sprint 12 flow never requires one.
    source_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    pm_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    cto_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    clarification_questions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    clarification_answers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Why planning most recently stopped (agreement / clarification_required
    # / blocking_feasibility / turn_limit / provider_error / ceo_action) --
    # observability for the CEO-facing status view (§4.9).
    stop_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    # Which orchestrator stage to re-run once the CEO answers a
    # clarification question (e.g. "pm_analysis" or "cto_review") -- set
    # only while status=clarification_required, cleared once resumed.
    resume_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpecificationVersionORM(Base):
    """One immutable, structured Project Specification draft (§4.5).
    Never updated in place once created -- a revision always inserts a new
    row and `SpecificationORM.current_version` is bumped to point at it
    (§4.8), so prior reviewable content and its approval/rejection history
    are never lost."""

    __tablename__ = "specification_versions"
    __table_args__ = (UniqueConstraint("specification_id", "version", name="uq_spec_version"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    specification_id: Mapped[str] = mapped_column(ForeignKey("specifications.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String)
    problem_statement: Mapped[str] = mapped_column(Text, default="")
    goals: Mapped[list] = mapped_column(JSON, default=list)
    non_goals: Mapped[list] = mapped_column(JSON, default=list)
    requirements: Mapped[list] = mapped_column(JSON, default=list)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    technical_approach: Mapped[str] = mapped_column(Text, default="")
    architecture_components: Mapped[list] = mapped_column(JSON, default=list)
    data_migration_impact: Mapped[str] = mapped_column(Text, default="")
    security_considerations: Mapped[str] = mapped_column(Text, default="")
    observability_requirements: Mapped[str] = mapped_column(Text, default="")
    test_plan: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[list] = mapped_column(JSON, default=list)  # [{"risk": ..., "mitigation": ...}]
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    unresolved_questions: Mapped[list] = mapped_column(JSON, default=list)
    implementation_stages: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class SpecificationTurnORM(Base):
    """One persisted PM or CTO planning contribution, or one CEO
    clarification answer (§4.3, §4.9). The authoritative, efficiently
    queryable "planning activity" list for the CEO-facing timeline --
    `SpecificationTurnPosted`/`SpecificationClarificationAnswered` events
    are still published alongside each row for the unified Timeline (Rule
    #8), but this table is what `GET .../turns` actually reads, the same
    division of labor `ApprovalORM` already has relative to its events.

    `role_key` is a data value copied from the resolved Employee's
    `AgentORM.role_key` at turn time (or None for a CEO-authored turn),
    never a hardcoded literal -- see Rule #16."""

    __tablename__ = "specification_turns"
    __table_args__ = (UniqueConstraint("specification_id", "turn_index", name="uq_spec_turn_index"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    specification_id: Mapped[str] = mapped_column(ForeignKey("specifications.id"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer)
    actor_role: Mapped[str] = mapped_column(String)  # "employee" | "ceo" (mirrors Actor.role)
    role_key: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String)  # analysis|review|clarification_request|clarification_answer|draft|revision
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ActiveSpecificationLockORM(Base):
    """Sprint 12 §5.3 concurrency guard, same shape as Sprint 11's
    `RoleSingletonLockORM`: one row per `project_id` exists exactly while
    that Company has a non-terminal Specification in flight. The
    single-column primary key (not a service-layer check-then-insert) is
    what makes two simultaneous "start planning"
    requests for the same Company race-safe -- both INSERT in the same
    transaction as their `SpecificationORM` row, the database allows
    exactly one to commit, and the loser's IntegrityError becomes
    `ActivePlanningExistsError`. Deleted (in the same transaction as the
    status write) the moment a Specification reaches a terminal status,
    freeing the Company to start a new planning run."""

    __tablename__ = "active_specification_locks"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    specification_id: Mapped[str] = mapped_column(ForeignKey("specifications.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
