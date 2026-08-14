"""agent last_assigned_at

Revision ID: 3c792f42c404
Revises: 91919bd41ac3
Create Date: 2026-08-14 13:50:17.241960

Sprint 10 Phase 3 §13: the role-to-employee resolver's tie-break rule
("longest since assigned") needs a per-Employee timestamp no existing
column captures. Nullable so existing rows (never yet resolved by the
new selection layer) read as "never assigned" -- the resolver treats
NULL as the oldest possible value, so untouched Employees are picked
first, which is the correct fairness behavior on upgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c792f42c404'
down_revision: Union[str, Sequence[str], None] = '91919bd41ac3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('agents') as batch_op:
        batch_op.add_column(sa.Column('last_assigned_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('agents') as batch_op:
        batch_op.drop_column('last_assigned_at')
