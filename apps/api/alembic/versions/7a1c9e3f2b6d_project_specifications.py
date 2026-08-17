"""project specifications

Revision ID: 7a1c9e3f2b6d
Revises: 3066d66c0064
Create Date: 2026-08-17 00:00:00.000000

Sprint 12 §4.5/§4.6/§5.3: adds the Project Specification domain -- the
`specifications` aggregate (planning run + reviewable document, one row per
CEO request), its immutable `specification_versions` lineage, the
`specification_turns` planning-activity log, and `active_specification_locks`
(the Sprint-11-style DB-backed one-active-run-per-project guard). Also adds
`tasks.specification_id`, nullable and NULL for every pre-Sprint-12 Mission,
recording provenance only for Missions created through the new gated
`POST /specifications/{id}/begin-execution` path.

No backfill: all four new tables are Sprint 12 concepts with no pre-existing
data, and every existing Mission legitimately has `specification_id = NULL`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1c9e3f2b6d'
down_revision: Union[str, Sequence[str], None] = '3066d66c0064'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "specifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("source_task_id", sa.String(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("pm_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("cto_agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clarification_questions", sa.JSON(), nullable=True),
        sa.Column("clarification_answers", sa.JSON(), nullable=True),
        sa.Column("stop_reason", sa.String(), nullable=True),
        sa.Column("resume_stage", sa.String(), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_specifications_project_id", "specifications", ["project_id"])
    op.create_index("ix_specifications_created_at", "specifications", ["created_at"])

    op.create_table(
        "specification_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("specification_id", sa.String(), sa.ForeignKey("specifications.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("problem_statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("non_goals", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("technical_approach", sa.Text(), nullable=False, server_default=""),
        sa.Column("architecture_components", sa.JSON(), nullable=False),
        sa.Column("data_migration_impact", sa.Text(), nullable=False, server_default=""),
        sa.Column("security_considerations", sa.Text(), nullable=False, server_default=""),
        sa.Column("observability_requirements", sa.Text(), nullable=False, server_default=""),
        sa.Column("test_plan", sa.Text(), nullable=False, server_default=""),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("unresolved_questions", sa.JSON(), nullable=False),
        sa.Column("implementation_stages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("specification_id", "version", name="uq_spec_version"),
    )
    op.create_index("ix_specification_versions_specification_id", "specification_versions", ["specification_id"])
    op.create_index("ix_specification_versions_created_at", "specification_versions", ["created_at"])

    op.create_table(
        "specification_turns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("specification_id", sa.String(), sa.ForeignKey("specifications.id"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("role_key", sa.String(), nullable=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("specification_id", "turn_index", name="uq_spec_turn_index"),
    )
    op.create_index("ix_specification_turns_specification_id", "specification_turns", ["specification_id"])
    op.create_index("ix_specification_turns_created_at", "specification_turns", ["created_at"])

    op.create_table(
        "active_specification_locks",
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("specification_id", sa.String(), sa.ForeignKey("specifications.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "specification_id",
            sa.String(),
            sa.ForeignKey(
                "specifications.id",
                use_alter=True,
                name="fk_tasks_specification_id",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tasks", "specification_id")
    op.drop_table("active_specification_locks")
    op.drop_index("ix_specification_turns_created_at", table_name="specification_turns")
    op.drop_index("ix_specification_turns_specification_id", table_name="specification_turns")
    op.drop_table("specification_turns")
    op.drop_index("ix_specification_versions_created_at", table_name="specification_versions")
    op.drop_index("ix_specification_versions_specification_id", table_name="specification_versions")
    op.drop_table("specification_versions")
    op.drop_index("ix_specifications_created_at", table_name="specifications")
    op.drop_index("ix_specifications_project_id", table_name="specifications")
    op.drop_table("specifications")
