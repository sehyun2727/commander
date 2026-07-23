"""Agent Runtime module.

Implements core.interfaces.agent_runtime.AgentRuntime. Owns every Employee
row (PM, Engineer, Reviewer) and validates their lifecycle transitions
against core.lifecycle.agent_states.AGENT_TRANSITIONS. Agents never call
each other directly — coordination happens only through the Event Bus.
"""

from .routes import router
from .service import DBAgentRuntime

__all__ = ["DBAgentRuntime", "router"]
