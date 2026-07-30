"""accounts and sessions

Revision ID: fa793dce62cb
Revises: 9fd1f513c939
Create Date: 2026-07-30 00:00:00.000000

DESTRUCTIVE (approved -- Sprint 9 brief §2.7 / docs/DECISIONS.md): every
existing `projects` row (and everything hanging off it -- agents, tasks,
approvals, cost_entries, reports) is deleted by this migration before
`projects.owner_id` is added as NOT NULL. There is no account to attach
pre-Sprint-9 companies to, and the brief explicitly authorizes discarding
local dev data rather than inventing a synthetic owner. `downgrade()` only
drops the columns/tables this migration added -- it does NOT restore the
deleted rows. That data is gone once this migration runs; there is no way
back except a pre-migration DB backup taken outside of Alembic.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa793dce62cb'
down_revision: Union[str, Sequence[str], None] = '9fd1f513c939'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('auth_provider', sa.String(), nullable=False),
        sa.Column('provider_subject', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('auth_provider', 'provider_subject', name='uq_users_auth_provider_subject'),
    )
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Existing project-hierarchy data has no account to belong to -- wipe it
    # (FK children first) before making projects.owner_id NOT NULL. Approved
    # destructive step, see this file's module docstring.
    op.execute('DELETE FROM cost_entries')
    op.execute('DELETE FROM approvals')
    op.execute('DELETE FROM reports')
    op.execute('DELETE FROM tasks')
    op.execute('DELETE FROM agents')
    op.execute('DELETE FROM projects')

    # batch_alter_table: SQLite has no ALTER TABLE ADD CONSTRAINT (only
    # Postgres does a plain in-place ALTER; SQLite gets the copy-and-move
    # recreate strategy transparently) -- config.py documents sqlite as a
    # supported "quick local runs" fallback, not just a test-only shim, so
    # this migration has to apply cleanly on both.
    with op.batch_alter_table('projects') as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.String(), nullable=False))
        batch_op.create_foreign_key('fk_projects_owner_id_users', 'users', ['owner_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema. Only reverses the schema shape -- the rows deleted
    by upgrade() are not recoverable."""
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_constraint('fk_projects_owner_id_users', type_='foreignkey')
        batch_op.drop_column('owner_id')
    op.drop_table('sessions')
    op.drop_table('users')
