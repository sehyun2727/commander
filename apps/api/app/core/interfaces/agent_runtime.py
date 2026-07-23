"""Port: how the Workflow Engine dispatches work to agents.

Concrete implementation lives in modules/agent_runtime. The Workflow Engine
depends only on this interface, never on a specific agent implementation.
"""

from abc import ABC, abstractmethod

from ..lifecycle.agent_states import AgentState


class AgentRuntime(ABC):
    @abstractmethod
    def dispatch(self, agent_role: str, task_id: str) -> str:
        """Hand a task to a fresh agent instance of the given role.
        Returns agent_id."""

    @abstractmethod
    def stop(self, agent_id: str) -> None:
        """Stop a running agent (e.g. after AgentTimeoutError — see
        FAILURE_HANDLING.md's recovery strategy: stop, then dispatch a
        fresh instance rather than resuming a stuck one)."""

    @abstractmethod
    def get_state(self, agent_id: str) -> AgentState:
        """Return an agent's current lifecycle state, for monitoring."""
