"""Turns an `AgentProfile` + role into the system prompt sent to a
provider. Pure function — no DB, no provider, no event-bus imports — so
it's trivially unit-testable and safe to call from any layer.

Layering contract (docs/DECISIONS.md, Sprint 4.5): personality/working/
decision traits, then custom instructions, then the immutable role
contract appended LAST. Nothing before the role contract can remove or
override it — that's what lets the Reviewer's Verdict requirement survive
any CEO-authored custom instruction.
"""

from __future__ import annotations

from ...core.contracts import AgentProfile
from .role_contracts import ROLE_CONTRACTS
from .traits import DECISION_STYLE_TRAITS, PERSONALITY_TRAITS, WORKING_STYLE_TRAITS


def build(profile: AgentProfile, role: str) -> str:
    sections = [
        PERSONALITY_TRAITS[profile.personality],
        WORKING_STYLE_TRAITS[profile.working_style],
        DECISION_STYLE_TRAITS[profile.decision_style],
    ]
    if profile.custom_instructions.strip():
        sections.append(f"CEO's custom instructions for you: {profile.custom_instructions.strip()}")
    sections.append(ROLE_CONTRACTS[role])
    return "\n\n".join(sections)
