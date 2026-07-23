"""Port: how the Workflow Engine drives an Employee's lifecycle.

Concrete implementation lives in modules/agent_runtime. The Workflow Engine
depends only on this interface, never reaching into agent_runtime's
internals directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..lifecycle.agent_states import AgentState


class AgentRuntime(ABC):
    @abstractmethod
    async def create_department(self, project_id: str) -> list[str]:
        """Create the default Department (PM, Engineer, Reviewer) for a
        freshly created project. Returns the three new agent ids."""

    @abstractmethod
    async def transition(self, agent_id: str, target: AgentState, reason: str) -> None:
        """Validate and apply agent_id's next lifecycle state, publishing
        AgentStateChanged (and AgentStarted/AgentStopped at the edges)."""

    @abstractmethod
    async def get_state(self, agent_id: str) -> AgentState:
        """Return an agent's current lifecycle state, for monitoring."""

    @abstractmethod
    async def set_current_task(self, agent_id: str, task_id: str | None) -> None:
        """Record which task (if any) an agent is presently working, so the
        Employees view can show "current Mission" without a join per call."""
