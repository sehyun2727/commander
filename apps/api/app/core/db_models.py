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

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String, default="mock")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentORM(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    role: Mapped[str] = mapped_column(String)  # "pm" | "engineer" | "reviewer"
    name: Mapped[str] = mapped_column(String)
    persona: Mapped[str] = mapped_column(Text)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SettingORM(Base):
    """Generic KV store for runtime-editable Company Settings (provider
    choice, secret overrides). Keyed per app instance, not per project —
    single local CEO, single company config surface for this sprint."""

    __tablename__ = "settings_kv"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)
