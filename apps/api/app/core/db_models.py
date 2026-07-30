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
    role: Mapped[str] = mapped_column(String)  # "pm" | "engineer" | "reviewer"
    name: Mapped[str] = mapped_column(String)
    profile: Mapped[dict] = mapped_column(JSON)  # AgentProfile.model_dump(mode="json")
    avatar_color: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="idle")
    current_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
