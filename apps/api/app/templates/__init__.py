"""Company templates.

A template is the single source of truth for a company's founding
Department: which roles exist, in what order the workflow runs them, each
role's founding identity and immutable prompt contract, and the default
`AgentProfile` each role is founded with. Sprint 4.7 (§10.6) ships exactly
one template (`software_company`) with no picker — hidden means ABSENT,
not a second template waiting to be un-hidden. Founding and the workflow
engine both read from it so no module branches on a hardcoded role name.
"""

from .software_company import TEMPLATE

__all__ = ["TEMPLATE"]
