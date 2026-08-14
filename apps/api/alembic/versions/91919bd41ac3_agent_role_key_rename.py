"""agent role_key rename

Revision ID: 91919bd41ac3
Revises: fa793dce62cb
Create Date: 2026-08-14 13:34:47.738739

Sprint 10 Phase B §9.1: `agents.role` is renamed to `agents.role_key` to
make explicit that it references `RoleSpec.key` (a template-owned Role
position), not an ad-hoc string. Pure rename, no data loss --
`batch_alter_table` so this applies cleanly on both SQLite (test/local
fallback) and Postgres (`make dev`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91919bd41ac3'
down_revision: Union[str, Sequence[str], None] = 'fa793dce62cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('agents') as batch_op:
        batch_op.alter_column('role', new_column_name='role_key', existing_type=sa.String())


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('agents') as batch_op:
        batch_op.alter_column('role_key', new_column_name='role', existing_type=sa.String())
