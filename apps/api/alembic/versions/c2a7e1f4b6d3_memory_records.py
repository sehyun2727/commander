"""memory records

Revision ID: c2a7e1f4b6d3
Revises: b1f4c8d5e9a2
Create Date: 2026-08-19 00:00:00.000000

Sprint 18 §4/§9, docs/DECISIONS.md #243: Project Memory is a deterministic
projection over already-persisted events (Rule #14) -- this table is the
only new schema this sprint introduces. `source_event_id` is UNIQUE so the
real-time subscriber and the idempotent `backfill_memory()` script are both
safe to run concurrently or repeatedly over the same event. New table
only -- no backfill needed at migration time (Phase 3 ships the optional
operator-run backfill script separately).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2a7e1f4b6d3'
down_revision: Union[str, Sequence[str], None] = 'b1f4c8d5e9a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.String(), sa.ForeignKey("events.id"), nullable=False, unique=True),
        sa.Column("source_task_id", sa.String(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("source_specification_id", sa.String(), sa.ForeignKey("specifications.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("keywords_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memory_records_project_id", "memory_records", ["project_id"])
    op.create_index("ix_memory_records_category", "memory_records", ["category"])
    op.create_index("ix_memory_records_source_task_id", "memory_records", ["source_task_id"])
    op.create_index(
        "ix_memory_records_source_specification_id", "memory_records", ["source_specification_id"]
    )
    op.create_index("ix_memory_records_created_at", "memory_records", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_memory_records_created_at", table_name="memory_records")
    op.drop_index("ix_memory_records_source_specification_id", table_name="memory_records")
    op.drop_index("ix_memory_records_source_task_id", table_name="memory_records")
    op.drop_index("ix_memory_records_category", table_name="memory_records")
    op.drop_index("ix_memory_records_project_id", table_name="memory_records")
    op.drop_table("memory_records")
