"""PromptBuilder module.

Pure functions turning an Employee's `AgentProfile` + role into the system
prompt sent to a provider. Generated prompts are never persisted — see
`builder.build`.
"""

from .builder import build
from .role_contracts import ROLE_CONTRACTS

__all__ = ["build", "ROLE_CONTRACTS"]
