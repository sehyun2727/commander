"""Deterministic-ish, zero-cost provider. Default provider (COMMANDER_
PROVIDER=mock) so the whole product works with no API key.

Templates are role-appropriate (inferred from the `model_ref` suffix set
by model_registry) with light randomness so repeated demos don't look
identical. Reviewer output always ends in an explicit Verdict line —
workflow_engine parses that line the same way for mock and real providers,
so swapping providers never changes orchestration logic.
"""

from __future__ import annotations

import random
from typing import Any

from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway

_PLAN_OPENERS = [
    "Here's how I'd break this down",
    "Plan for this mission",
    "Proposed approach",
]

_STEP_VERBS = [
    "Clarify the requirements and constraints for",
    "Draft the core approach for",
    "Identify edge cases and risks in",
    "Implement the primary flow for",
    "Write tests / a verification checklist for",
    "Prepare a short handoff summary for",
]

_DELIVERABLE_NOTES = [
    "Kept the change scoped to what the mission asked for.",
    "Flagged one open question for the PM in the notes below.",
    "Reused existing patterns already in the codebase where possible.",
    "This is ready for review; no known blockers.",
]

_AUDIT_CHECKS = [
    "Matches the PM's plan",
    "No obvious regressions introduced",
    "Reasoning is explained, not just asserted",
    "Scope matches the mission brief (no drive-by changes)",
]


def _role_from_ref(model_ref: str) -> str:
    if "planner" in model_ref:
        return "planner"
    if "builder" in model_ref:
        return "builder"
    return "reviewer"


def _plan_text(title: str, description: str) -> str:
    steps = random.sample(_STEP_VERBS, k=random.randint(3, 5))
    numbered = "\n".join(f"{i}. {verb} **{title}**." for i, verb in enumerate(steps, 1))
    opener = random.choice(_PLAN_OPENERS)
    extra = f"\n\nContext: {description}" if description else ""
    return f"{opener}:\n\n{numbered}{extra}"


def _deliverable_text(title: str, description: str, context: str) -> str:
    note = random.choice(_DELIVERABLE_NOTES)
    plan_ref = f"\n\nFollowing the plan:\n> {context.strip().splitlines()[0]}" if context else ""
    return (
        f"## Deliverable: {title}\n\n"
        f"**Summary:** Implemented the work described in this mission.{plan_ref}\n\n"
        f"**Changes:**\n- Addressed the primary requirement in \"{title}\".\n"
        f"- {description or 'No further description was provided.'}\n\n"
        f"**Notes:** {note}"
    )


def _audit_text(title: str, context: str) -> str:
    checks = "\n".join(f"- [x] {c}" for c in _AUDIT_CHECKS)
    approved = random.random() < 0.7
    verdict = "Approved" if approved else "Changes requested"
    concern = (
        ""
        if approved
        else "\n\n**Requested change:** please add more detail to the deliverable before re-review."
    )
    return (
        f"## Audit: {title}\n\n{checks}{concern}\n\n**Verdict:** {verdict}"
    )


class MockProvider(ProviderGateway):
    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        role = _role_from_ref(model_ref)
        title = opts.get("task_title", "this mission")
        description = opts.get("task_description", "")
        context = opts.get("context", "")

        if role == "planner":
            text = _plan_text(title, description)
        elif role == "builder":
            text = _deliverable_text(title, description, context)
        else:
            text = _audit_text(title, context)

        return CompletionResult(text=text, model=model_ref, provider="mock")
