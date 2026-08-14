"""employee singleton locks

Revision ID: 3066d66c0064
Revises: 3c792f42c404
Create Date: 2026-08-14 15:23:27.135677

Sprint 11 §4.10: a hiring route now reaches `create_employee`/`hire_employee`,
so the Sprint 10 service-layer check-then-insert is no longer an acceptable
singleton guarantee on its own (docs/DECISIONS.md #167). This migration adds
`role_singleton_locks`: one row per (project_id, role_key) for every
singleton Role that currently has an Employee, keyed by a composite primary
key so the database itself -- not application logic -- rejects a second
concurrent insert for the same company/Role with an IntegrityError.

Backfill: every pre-Sprint-11 company was founded with exactly one PM and
one Reviewer (the only singleton Roles that could exist before CTO was
added), so this migration seeds a lock row for each existing PM/Reviewer
Employee. The role-key/model_ref values below are a snapshot of Sprint 10's
software_company template at migration time, not a live import of
app.templates -- a migration must remain correct even if the template
changes again later.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3066d66c0064'
down_revision: Union[str, Sequence[str], None] = '3c792f42c404'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sprint 10's only two singleton Role keys that could have an Employee
# before this migration runs (CTO is Sprint 11 data, always vacant at
# migration time -- see docs/DECISIONS.md #178).
_PRE_SPRINT_11_SINGLETON_ROLE_KEYS = ("pm", "reviewer")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "role_singleton_locks",
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("role_key", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    conn = op.get_bind()
    agents = sa.table(
        "agents",
        sa.column("id", sa.String()),
        sa.column("project_id", sa.String()),
        sa.column("role_key", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    locks = sa.table(
        "role_singleton_locks",
        sa.column("project_id", sa.String()),
        sa.column("role_key", sa.String()),
        sa.column("agent_id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    existing = conn.execute(
        sa.select(agents.c.id, agents.c.project_id, agents.c.role_key, agents.c.created_at).where(
            agents.c.role_key.in_(_PRE_SPRINT_11_SINGLETON_ROLE_KEYS)
        )
    ).fetchall()
    if existing:
        conn.execute(
            locks.insert(),
            [
                {"project_id": row.project_id, "role_key": row.role_key, "agent_id": row.id, "created_at": row.created_at}
                for row in existing
            ],
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("role_singleton_locks")
