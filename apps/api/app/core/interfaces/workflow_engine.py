"""Port: the Workflow Engine — Commander's orchestration brain.

Concrete implementation lives in modules/workflow_engine. The API layer
depends only on this interface — per docs/ARCHITECTURE.md, "no AI logic
exists" in the API Server itself.

Sprint 3 scopes this to the one pipeline the vertical slice needs: a task
moves PM (plan) -> Engineer (build) -> Reviewer (audit) -> CEO Decision.
`handle_ceo_request`'s free-text intent parsing from the Sprint 1 draft is
out of scope this sprint (Missions are created directly from the UI); see
docs/DECISIONS.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class WorkflowEngine(ABC):
    @abstractmethod
    async def start_task(self, task_id: str) -> None:
        """Run the PM -> Engineer -> Reviewer pipeline for a newly assigned
        task, ending in an Approval request. Runs in the background so the
        API stays responsive; safe to fire-and-forget."""

    @abstractmethod
    async def resume_after_decision(
        self, task_id: str, decision: str, comment: str | None
    ) -> None:
        """React to a CEO Decision on a task's approval: complete it,
        cancel it, or send it back to the Engineer for rework."""
