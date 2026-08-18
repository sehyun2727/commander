"""workspace preferences

Revision ID: 77037fd534fa
Revises: 7a1c9e3f2b6d
Create Date: 2026-08-18 14:11:25.703976

Sprint 15 §5, docs/DECISIONS.md #228: one CEO Workspace widget layout per
(user, company). New table only -- no backfill needed. Existing CEOs get
their default layout lazily on first `GET .../workspace/preferences`
(`service.get_effective_preferences`), same pattern the rest of this
codebase already uses for "no row yet" (e.g. no pre-seeded `settings_kv`
rows either).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77037fd534fa'
down_revision: Union[str, Sequence[str], None] = '7a1c9e3f2b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workspace_preferences",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("widgets", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "project_id", name="uq_workspace_preferences_user_project"),
    )
    op.create_index("ix_workspace_preferences_user_id", "workspace_preferences", ["user_id"])
    op.create_index("ix_workspace_preferences_project_id", "workspace_preferences", ["project_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_workspace_preferences_project_id", table_name="workspace_preferences")
    op.drop_index("ix_workspace_preferences_user_id", table_name="workspace_preferences")
    op.drop_table("workspace_preferences")
