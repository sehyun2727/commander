"""Deterministic-ish, zero-cost provider. Default provider (COMMANDER_
PROVIDER=mock) so the whole product works with no API key.

Templates are role-appropriate (inferred from the `model_ref` suffix set
by model_registry) with light randomness so repeated demos don't look
identical. Reviewer output always ends in an explicit Verdict line —
workflow_engine parses that line the same way for mock and real providers,
so swapping providers never changes orchestration logic.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, AsyncIterator

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

_RISKS_IF_APPROVED = [
    "Scope could creep on the next mission if this precedent isn't documented.",
    "No automated test coverage for this yet, so a regression could slip through.",
    "Low risk -- the change is small and easy to revert.",
]

_IMPACTS = [
    "Moves the mission off the CEO's plate and into Completed.",
    "Unblocks whatever mission was waiting on this one.",
    "Small, incremental progress toward the company's goals.",
]


def _role_from_ref(model_ref: str) -> str:
    if "planner" in model_ref:
        return "planner"
    if "builder" in model_ref:
        return "builder"
    if "reporter" in model_ref:
        return "reporter"
    if "situation" in model_ref:
        return "situation"
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


# Marker string unique to the code-mission Engineer contract (see
# app/templates/software_company.py _ENGINEER_CONTRACT_CODE) -- sniffing
# it from the system prompt lets the mock provider pick the right output
# shape without workflow_engine having to pass deliverable_type through
# `opts` separately. Same technique _flavor_suffix already uses below.
_CODE_CONTRACT_MARKER = "===== FILE:"


def _code_deliverable_text(title: str, description: str, context: str) -> str:
    """Deterministic 2-file static-site output for code missions. Re-runs
    (context carries the "CEO feedback to address" marker _run_role adds
    on request-changes) produce a plausibly-edited variant rather than
    identical content, so the second commit on the branch has a real diff."""
    is_revision = "CEO feedback to address" in context
    heading = (title.strip() or "Mission")[:40]
    tagline = description.strip() or f"A small static page for {heading}."
    accent = "#16a34a" if is_revision else "#2563eb"

    if is_revision:
        feedback = context.split("CEO feedback to address:", 1)[-1].strip().splitlines()[0][:120]
        summary = (
            f"Updated the {heading} page to address the CEO's feedback ({feedback}). "
            "Refreshed the accent color and tightened the hero copy; the page "
            "structure is unchanged, so this should be a low-risk follow-up. "
            "Note: this is still simulated, placeholder output, not a real second pass."
        )
    else:
        summary = (
            f"Added a small static landing page for \"{heading}\": a hero section, a "
            "one-line tagline, and a stylesheet. Kept it to two files since this is "
            "a first pass. Risk: the copy is placeholder and will need a real pass "
            "before it's public-facing."
        )

    index_html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{heading}</title>\n"
        "  <link rel=\"stylesheet\" href=\"style.css\">\n"
        "</head>\n"
        "<body>\n"
        "  <main class=\"hero\">\n"
        f"    <h1>{heading}</h1>\n"
        f"    <p>{tagline}</p>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )
    style_css = (
        "body { font-family: sans-serif; margin: 0; }\n"
        f".hero {{ padding: 4rem 2rem; text-align: center; color: {accent}; }}\n"
        ".hero h1 { font-size: 2rem; margin-bottom: 0.5rem; }\n"
    )

    return (
        f"**Change Summary:** {summary}\n\n"
        f"===== FILE: index.html =====\n{index_html}===== END FILE =====\n\n"
        f"===== FILE: style.css =====\n{style_css}===== END FILE ====="
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
    problem = f"The mission needed someone to deliver \"{title}\" and have it verified before shipping."
    recommendation = (
        f"Approve the deliverable for \"{title}\" as submitted."
        if approved
        else f"Send \"{title}\" back for one more pass before approving."
    )
    risk = random.choice(_RISKS_IF_APPROVED)
    impact = random.choice(_IMPACTS)
    return (
        f"## Audit: {title}\n\n"
        f"**Problem:** {problem}\n\n"
        f"**Recommendation:** {recommendation}\n\n"
        f"**Risk:** {risk}\n\n"
        f"**Impact:** {impact}\n\n"
        f"{checks}{concern}\n\n"
        f"_Simulated review (mock provider) — a scripted placeholder pass, not a verified real audit._"
        f"\n\n**Verdict:** {verdict}"
    )


def _report_text(opts: dict[str, Any]) -> str:
    period_label = opts.get("period_label", "the last 24 hours")
    completed = opts.get("missions_completed", 0)
    failed = opts.get("missions_failed", 0)
    decisions = opts.get("decisions_made", 0)
    payroll_usd = opts.get("payroll_usd", 0.0)
    highlights = opts.get("highlights") or []

    if completed or failed or decisions:
        activity = (
            f"Over {period_label}, the team closed out {completed} mission"
            f"{'s' if completed != 1 else ''}"
            + (f", hit {failed} setback{'s' if failed != 1 else ''}" if failed else "")
            + f", and the CEO made {decisions} decision{'s' if decisions != 1 else ''}."
        )
    else:
        activity = f"It was a quiet stretch over {period_label} — no missions moved and no decisions were needed."

    lines = [f"## Daily Report — {period_label}", "", activity]
    if highlights:
        lines += ["", "**Highlights:**", *[f"- {h}" for h in highlights[:5]]]
    payroll_str = f"${payroll_usd:.4f}" if payroll_usd < 0.01 else f"${payroll_usd:.2f}"
    lines += ["", f"**Payroll this period:** {payroll_str}"]
    return "\n".join(lines)


def _situation_text(opts: dict[str, Any]) -> str:
    pending = opts.get("pending_decisions", 0)
    active = opts.get("missions_active", 0)
    last_reason = opts.get("last_event_reason")

    pieces = []
    if pending:
        pieces.append(f"{pending} decision{'s' if pending != 1 else ''} waiting on you")
    if active:
        pieces.append(f"{active} mission{'s' if active != 1 else ''} in flight")

    if not pieces:
        base = "Everything's quiet right now — no missions in flight and nothing needs your decision."
    else:
        base = "Right now: " + ", ".join(pieces) + "."
    if last_reason:
        base += f" Most recently: {last_reason}."
    return base


def _flavor_suffix(system: str) -> str:
    """Light personality flavor sniffed from the system prompt's trait text
    (see prompt_builder.traits) — mock provider has no real model to steer
    with a system prompt, so this is the only visible sign a CEO's profile
    edit changed anything in mock mode."""
    if "risk-aware" in system or "risk-avoiding" in system:
        return " (Flagging as a precaution: worth a second look before this ships.)"
    if "friendly and warm" in system:
        return " Thanks for trusting me with this one!"
    if "direct and blunt" in system:
        return " Bottom line: this is done."
    return ""


def _text_for(model_ref: str, system: str, opts: dict[str, Any]) -> str:
    role = _role_from_ref(model_ref)
    if role == "reporter":
        return _report_text(opts)
    if role == "situation":
        return _situation_text(opts)
    title = opts.get("task_title", "this mission")
    description = opts.get("task_description", "")
    context = opts.get("context", "")

    if role == "planner":
        return _plan_text(title, description) + _flavor_suffix(system)
    if role == "builder":
        if _CODE_CONTRACT_MARKER in system:
            return _code_deliverable_text(title, description, context)
        return _deliverable_text(title, description, context) + _flavor_suffix(system)
    # Reviewer output must end in the trailing "**Verdict:** ..." line
    # (workflow_engine parses it verbatim) — never append flavor text after it.
    return _audit_text(title, context)


def _fabricate_usage(system: str, messages: list[dict[str, str]], text: str) -> dict[str, int]:
    prompt_words = len(system.split()) + sum(len(m.get("content", "").split()) for m in messages)
    return {
        "input_tokens": max(1, int(prompt_words * 1.3)),
        "output_tokens": max(1, int(len(text.split()) * 1.3)),
    }


class MockProvider(ProviderGateway):
    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        text = _text_for(model_ref, system, opts)
        usage = _fabricate_usage(system, messages, text)
        return CompletionResult(
            text=text,
            model=model_ref,
            provider="mock",
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
        )

    async def stream(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        usage: dict[str, int] | None = None,
        **opts: Any,
    ) -> AsyncIterator[str]:
        text = _text_for(model_ref, system, opts)
        fabricated = _fabricate_usage(system, messages, text)
        if usage is not None:
            usage.update(fabricated)

        words = text.split(" ")
        delay = opts.get("stream_delay", 0.015)
        for i, word in enumerate(words):
            yield word if i == 0 else " " + word
            if delay:
                await asyncio.sleep(delay)
