"""harness tool calls

Revision ID: b1f4c8d5e9a2
Revises: 77037fd534fa
Create Date: 2026-08-18 15:00:00.000000

Sprint 16 §4/§9, docs/DECISIONS.md #233: durable audit persistence for
Agent Harness tool calls, independent of in-memory tool-loop state.
`arguments_summary` deliberately never stores full file content -- only a
bounded, tool-specific summary (see app/modules/agent_harness/audit.py).
New table only -- no backfill needed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f4c8d5e9a2'
down_revision: Union[str, Sequence[str], None] = '77037fd534fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "harness_tool_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("call_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("arguments_summary", sa.JSON(), nullable=False),
        sa.Column("output_excerpt", sa.Text(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_harness_tool_calls_project_id", "harness_tool_calls", ["project_id"])
    op.create_index("ix_harness_tool_calls_task_id", "harness_tool_calls", ["task_id"])
    op.create_index("ix_harness_tool_calls_agent_id", "harness_tool_calls", ["agent_id"])
    op.create_index("ix_harness_tool_calls_created_at", "harness_tool_calls", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_harness_tool_calls_created_at", table_name="harness_tool_calls")
    op.drop_index("ix_harness_tool_calls_agent_id", table_name="harness_tool_calls")
    op.drop_index("ix_harness_tool_calls_task_id", table_name="harness_tool_calls")
    op.drop_index("ix_harness_tool_calls_project_id", table_name="harness_tool_calls")
    op.drop_table("harness_tool_calls")
