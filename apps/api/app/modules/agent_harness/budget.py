"""Tool-loop budget guard for the Agent Harness (Sprint 16 §4.9, Rule #13,
DECISIONS.md #233).

Checked in addition to (not instead of) the existing mission-level
token/USD/wall-time budget (`workflow_engine.engine._check_budget`);
harness exhaustion raises the same `BudgetExceededError` with a new
`limit_kind` ("tool_calls" or "seconds"), so it reaches the mission the
same block-with-reason path the mission budget already uses -- never a
silent stop, never an unbounded retry (Rule #13).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ...core.config import settings
from ...core.errors import BudgetExceededError


@dataclass
class HarnessBudget:
    """Mutable per-tool-loop counters. One instance per Engineer tool-loop
    attempt; never shared across missions or reused across attempts."""

    stage: str
    max_tool_calls: int = field(default_factory=lambda: settings.commander_harness_max_tool_calls)
    max_seconds: int = field(default_factory=lambda: settings.commander_harness_max_seconds)
    _started_at: float = field(default_factory=time.monotonic, repr=False)
    tool_calls_made: int = 0

    def record_tool_call(self) -> None:
        self.tool_calls_made += 1

    def check(self) -> None:
        """Raise `BudgetExceededError` if either cap has been exceeded.
        Call this before every tool-loop iteration, mirroring
        `_check_budget`'s "checked before each stage starts" contract."""
        if self.tool_calls_made > self.max_tool_calls:
            raise BudgetExceededError("tool_calls", self.max_tool_calls, self.tool_calls_made, self.stage)
        elapsed = time.monotonic() - self._started_at
        if elapsed > self.max_seconds:
            raise BudgetExceededError("seconds", self.max_seconds, elapsed, self.stage)
