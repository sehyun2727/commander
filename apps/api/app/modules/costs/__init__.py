"""Costs module (Payroll).

Records one row per provider call (usage + USD cost) and summarizes it per
Company and per Mission. Purely derived telemetry — it never publishes to
the Event Bus and other modules never read `CostEntryORM` directly; they go
through `record_usage`/`summary_for_*` here.
"""

from .routes import router
from .service import record_usage, summary_since, usage_for_task

__all__ = ["router", "record_usage", "summary_since", "usage_for_task"]
