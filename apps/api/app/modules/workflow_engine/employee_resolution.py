"""Sprint 10 §12: the single place that decides *which* Employee of a Role
runs a pipeline stage, now that a Role may hold more than one Employee
(§9.2). Sprint 12 replaces this selection layer with the PM's explicit
assignment -- callers must keep depending on `resolve_employee_for_role`
rather than reimplementing the rule, so that swap only ever touches this
file.

Sprint 10 §12.1 fixes the rule for this sprint:
    1. Prefer an idle Employee.
    2. Among the eligible pool, pick whoever has gone longest without
       being assigned (`last_assigned_at` ascending; NULL sorts first,
       since "never assigned" is the longest possible wait).
    3. If no Employee is idle, fall back to the same tie-break rule over
       every Employee holding the Role.

§13 requires the tie-break to be fully deterministic: `last_assigned_at`
-> `created_at` -> `id` (the stable primary key), so two Employees with
identical timestamps still resolve the same way every time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Sequence

from ...core.db_models import AgentORM
from ...core.lifecycle.agent_states import AgentState

ResolutionRule = Literal["idle", "no_idle_fallback"]


def _tie_break_key(agent: AgentORM) -> tuple[int, datetime, datetime, str]:
    # A never-assigned Employee (`last_assigned_at is None`) has waited
    # longer than any Employee with a real timestamp, so the "ever
    # assigned" flag is compared first -- this also sidesteps SQLite
    # returning naive datetimes for `DateTime(timezone=True)` columns
    # (a synthetic min-datetime sentinel would need to be tz-aware to
    # compare against Postgres's aware values, which then fails against
    # SQLite's naive ones; comparing only real, same-column values never
    # hits that mismatch).
    ever_assigned = agent.last_assigned_at is not None
    return (int(ever_assigned), agent.last_assigned_at or agent.created_at, agent.created_at, agent.id)


def resolve_employee_for_role(candidates: Sequence[AgentORM]) -> tuple[AgentORM, ResolutionRule]:
    """Pick one Employee from `candidates` (all Employees holding the same
    Role) per the Sprint 10 §12.1 rule. Raises `ValueError` if `candidates`
    is empty -- every Role always has at least its founding Employee, so an
    empty pool means the caller queried the wrong Role."""
    if not candidates:
        raise ValueError("resolve_employee_for_role: no candidates")

    idle = [agent for agent in candidates if agent.state == AgentState.IDLE.value]
    pool, rule = (idle, "idle") if idle else (list(candidates), "no_idle_fallback")
    selected = min(pool, key=_tie_break_key)
    return selected, rule
