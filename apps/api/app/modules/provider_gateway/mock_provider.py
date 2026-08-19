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
import json
import random
from typing import Any, AsyncIterator

from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway, ToolCallData

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
    # "advisor" is a mock-only voice label, deliberately not the RoleSpec
    # key "cto" -- see docs/DECISIONS.md #196 (Rule #16).
    if "advisor" in model_ref:
        return "advisor"
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


# --- Sprint 12: PM<->CTO planning turns ------------------------------------
#
# Every planning turn is requested via `gateway.complete(..., planning_turn_
# kind=...)` and must return a single JSON object (see the *_PLANNING_
# CONTRACT text in app/templates/software_company.py) -- the orchestrator
# parses it, never free text. These fixture markers are literal substrings
# of the CEO's original request_text, giving tests a deterministic way to
# steer mock planning down the clarification/follow-up/blocking paths
# without needing a real provider (§4.11). `already_resumed` (passed by the
# orchestrator once it re-enters a stage after the CEO answered a
# clarification question) suppresses every marker so a resumed turn can't
# re-trigger the same pause forever.
NEEDS_CLARIFICATION_MARKER = "NEEDS_CLARIFICATION"
BLOCKING_FEASIBILITY_MARKER = "BLOCKING_FEASIBILITY_ISSUE"
CTO_FOLLOWUP_MARKER = "CTO_FOLLOWUP_NEEDED"


def _mock_specification_fields(request_text: str, note: str = "") -> dict[str, Any]:
    """One deterministic, fully-populated Specification draft. Reused by
    every turn kind that ends in a draft (`pm_draft_or_followup` when ready,
    `pm_draft`, `pm_revision_draft`) so mock mode always produces every
    field the schema requires (§4.5)."""
    seed = (request_text.strip() or "the CEO's request")[:80]
    return {
        "title": f"Specification: {seed}",
        "problem_statement": f"The CEO asked for: {seed}.{(' ' + note) if note else ''}",
        "goals": [f"Deliver what the CEO described: {seed}", "Ship something the Reviewer can audit"],
        "non_goals": ["Anything not explicitly requested in the CEO's prompt"],
        "requirements": [f"Implement the core behavior described in: {seed}"],
        "acceptance_criteria": ["The Engineer's deliverable satisfies every listed requirement"],
        "technical_approach": "Simulated technical approach (mock provider) -- a scripted placeholder, not a real design.",
        "architecture_components": ["Existing pipeline (PM -> Engineer -> Reviewer)"],
        "data_migration_impact": "None expected for this request.",
        "security_considerations": "No new secrets, credentials, or external surfaces introduced.",
        "observability_requirements": "Standard Timeline events already emitted by the pipeline are sufficient.",
        "test_plan": "Reviewer audit plus any automated checks the template already runs.",
        "risks": [{"risk": "Requirements may be under-specified.", "mitigation": "PM/CTO planning already surfaced open questions below."}],
        "dependencies": [],
        "assumptions": ["The CEO's request text is authoritative for scope."],
        "unresolved_questions": [],
        "implementation_stages": ["Single mission through the existing pipeline"],
    }


def _pm_analysis_text(opts: dict[str, Any]) -> str:
    request_text = opts.get("request_text", "")
    already_resumed = bool(opts.get("already_resumed"))
    needs_clarification = NEEDS_CLARIFICATION_MARKER in request_text and not already_resumed
    payload = {
        "needs_clarification": needs_clarification,
        "questions": (
            ["What does success look like for this request?", "Are there any constraints the CTO should know about?"]
            if needs_clarification
            else []
        ),
        "analysis_summary": f"PM analysis: the CEO's request is \"{request_text.strip()[:200]}\".",
    }
    return json.dumps(payload)


def _cto_review_text(opts: dict[str, Any]) -> str:
    request_text = opts.get("request_text", "")
    already_resumed = bool(opts.get("already_resumed"))
    blocking = BLOCKING_FEASIBILITY_MARKER in request_text and not already_resumed
    payload = {
        "blocking": blocking,
        "blocking_reason": (
            "This request is not technically feasible with the current architecture." if blocking else None
        ),
        "risks": [] if blocking else ["Low risk -- fits the existing pipeline."],
        "architecture_notes": (
            "N/A -- blocked before an architecture could be proposed."
            if blocking
            else "Fits the existing PM -> Engineer -> Reviewer pipeline with no new components."
        ),
    }
    return json.dumps(payload)


def _pm_draft_or_followup_text(opts: dict[str, Any]) -> str:
    request_text = opts.get("request_text", "")
    followup_used = bool(opts.get("followup_used"))
    needs_followup = CTO_FOLLOWUP_MARKER in request_text and not followup_used
    if needs_followup:
        payload: dict[str, Any] = {
            "ready_to_draft": False,
            "follow_up_question": "Can you confirm the exact scope boundary for this request?",
            "specification": None,
        }
    else:
        payload = {
            "ready_to_draft": True,
            "follow_up_question": None,
            "specification": _mock_specification_fields(request_text),
        }
    return json.dumps(payload)


def _cto_followup_answer_text(opts: dict[str, Any]) -> str:
    question = opts.get("follow_up_question", "")
    return json.dumps({"answer": f"Scope confirmed as described; answering: {question.strip()[:200]}"})


def _pm_draft_text(opts: dict[str, Any]) -> str:
    request_text = opts.get("request_text", "")
    follow_up_answer = opts.get("follow_up_answer", "")
    note = f"Incorporated CTO follow-up answer: {follow_up_answer}" if follow_up_answer else ""
    return json.dumps({"specification": _mock_specification_fields(request_text, note)})


def _pm_revision_draft_text(opts: dict[str, Any]) -> str:
    request_text = opts.get("request_text", "")
    feedback = opts.get("revision_feedback", "")
    note = f"Revised per CEO feedback: {feedback.strip()}" if feedback else ""
    return json.dumps({"specification": _mock_specification_fields(request_text, note)})


_PLANNING_TEXT_BY_KIND = {
    "pm_analysis": _pm_analysis_text,
    "cto_review": _cto_review_text,
    "pm_draft_or_followup": _pm_draft_or_followup_text,
    "cto_followup_answer": _cto_followup_answer_text,
    "pm_draft": _pm_draft_text,
    "pm_revision_draft": _pm_revision_draft_text,
}


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
    planning_turn_kind = opts.get("planning_turn_kind")
    if planning_turn_kind is not None:
        return _PLANNING_TEXT_BY_KIND[planning_turn_kind](opts)

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


def _content_word_count(content: Any) -> int:
    """Tool-loop messages carry a list of content blocks (text/tool_use/
    tool_result), not a plain string -- unlike every pre-Sprint-16 message,
    which is always `{"role": ..., "content": "some string"}`. Handle both
    shapes rather than assuming `.split()` exists on `content`."""
    if isinstance(content, str):
        return len(content.split())
    if isinstance(content, list):
        return sum(len(str(block).split()) for block in content)
    return 0


def _fabricate_usage(system: str, messages: list[dict[str, str]], text: str) -> dict[str, int]:
    prompt_words = len(system.split()) + sum(_content_word_count(m.get("content", "")) for m in messages)
    return {
        "input_tokens": max(1, int(prompt_words * 1.3)),
        "output_tokens": max(1, int(len(text.split()) * 1.3)),
    }


# --- Sprint 16: Agent Harness deterministic tool-loop scenarios -----------
#
# A harness call is any `gateway.complete(..., tools=[...])` -- the mock
# never sees role/skill/permission data (it has none), only the shape of
# the call itself. `messages` grows by exactly two entries per iteration
# (one assistant tool_use turn, one user tool_result turn), so
# `len(messages)` alone is a deterministic turn counter -- no fixture flag
# needed to exercise repository read, patch, validation, and completion in
# order (§7). "denied call" and "budget exhaustion" are exercised by
# varying the *permission*/*budget* inputs around this fixed sequence, not
# by a special branch here (see test_agent_harness_orchestrator.py) --
# DECISIONS.md #235.
_MOCK_INDEX_HTML = (
    "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n"
    "  <title>Harness Demo</title>\n  <link rel=\"stylesheet\" href=\"style.css\">\n"
    "</head>\n<body>\n  <main class=\"hero\">\n    <h1>Harness Demo</h1>\n"
    "    <p>Built by the Engineer's tool loop.</p>\n  </main>\n</body>\n</html>\n"
)
_MOCK_STYLE_CSS = (
    "body { font-family: sans-serif; margin: 0; }\n"
    ".hero { padding: 4rem 2rem; text-align: center; color: #2563eb; }\n"
    ".hero h1 { font-size: 2rem; margin-bottom: 0.5rem; }\n"
)


def _is_rework(messages: list[dict]) -> bool:
    """The initial user message embeds `CEO feedback to address: ...`
    (`workflow_engine._run_engineer_tool_loop`) whenever this attempt is a
    rework -- used so a rework attempt writes genuinely different content
    instead of re-applying byte-identical files (which `apply_patch` now
    treats as a no-op, per DECISIONS.md #235's "apply_patch commit()
    ValueError" fix)."""
    first = messages[0].get("content", "") if messages else ""
    if isinstance(first, list):
        first = " ".join(str(block) for block in first)
    return "CEO feedback to address" in str(first)


# --- Sprint 17: self-correction mock scenarios (DECISIONS.md #239) --------
#
# A CEO/test can steer the deterministic tool-loop script by embedding one
# of these markers in the mission title/description -- same fixture-marker
# technique the planning turns above already use (NEEDS_CLARIFICATION_
# MARKER etc.), detected from `messages[0]`, the initial user message,
# which is always a plain string (`_run_engineer_tool_loop` builds it as
# f"Mission: {task.title}\n{task.description}...", never a content-block
# list). `SELF_CORRECTION_EXHAUSTED`/`SELF_CORRECTION_SURRENDER` are
# deliberately not scripted here -- §4.15/Phase 3 item 12 covers those
# paths as orchestrator-level `FakeGateway` tests instead
# (test_agent_harness_orchestrator.py), since a full pipeline run adds no
# additional coverage over the loop mechanics those tests already exercise
# directly.
SELF_CORRECTION_DEMO_MARKER = "SELF_CORRECTION_DEMO"
SELF_CORRECTION_ROLLBACK_MARKER = "SELF_CORRECTION_ROLLBACK"


def _self_correction_demo_response(turn: int, call_id: str) -> tuple[str, tuple[ToolCallData, ...]]:
    """A well-behaved Employee that reacts to a failed validation on its
    own -- no server interception needed: read, patch, validate (the
    test's steerable sandbox fails this one), patch again to fix it,
    validate again (passes), then a normal termination."""
    if turn == 0:
        return "", (ToolCallData(call_id, "read_file", {"path": "README.md"}),)
    if turn == 1:
        return "", (
            ToolCallData(
                call_id,
                "apply_patch",
                {"files": [{"path": "index.html", "content": "<html><body>missing head</body></html>\n"}]},
            ),
        )
    if turn == 2:
        return "", (ToolCallData(call_id, "run_validation", {"profile": "python-syntax"}),)
    if turn == 3:
        return "", (
            ToolCallData(call_id, "apply_patch", {"files": [{"path": "index.html", "content": _MOCK_INDEX_HTML}]}),
        )
    if turn == 4:
        return "", (ToolCallData(call_id, "run_validation", {"profile": "python-syntax"}),)
    summary = (
        "Self-correction demo: the first attempt failed validation, so the "
        "Employee fixed index.html and re-ran validation before finishing."
    )
    return f"**Change Summary:** {summary}", ()


def _self_correction_rollback_response(turn: int, call_id: str) -> tuple[str, tuple[ToolCallData, ...]]:
    """The Employee undoes a failed patch with `revert_last_patch` rather
    than editing over it, then lands a different fix."""
    if turn == 0:
        return "", (ToolCallData(call_id, "read_file", {"path": "README.md"}),)
    if turn == 1:
        return "", (
            ToolCallData(call_id, "apply_patch", {"files": [{"path": "index.html", "content": "<html>broken markup\n"}]}),
        )
    if turn == 2:
        return "", (ToolCallData(call_id, "run_validation", {"profile": "python-syntax"}),)
    if turn == 3:
        return "", (ToolCallData(call_id, "revert_last_patch", {}),)
    if turn == 4:
        return "", (
            ToolCallData(
                call_id,
                "apply_patch",
                {"files": [{"path": "index.html", "content": _MOCK_INDEX_HTML}, {"path": "style.css", "content": _MOCK_STYLE_CSS}]},
            ),
        )
    if turn == 5:
        return "", (ToolCallData(call_id, "run_validation", {"profile": "python-syntax"}),)
    summary = (
        "Self-correction rollback demo: the first patch failed validation, so "
        "the Employee reverted it with revert_last_patch and landed a "
        "different fix instead of editing over the broken version."
    )
    return f"**Change Summary:** {summary}", ()


def _tool_loop_response(messages: list[dict]) -> tuple[str, tuple[ToolCallData, ...]]:
    turn = (len(messages) - 1) // 2
    call_id = f"mock-call-{turn}"
    first_content = str(messages[0].get("content", "")) if messages else ""
    if SELF_CORRECTION_DEMO_MARKER in first_content:
        return _self_correction_demo_response(turn, call_id)
    if SELF_CORRECTION_ROLLBACK_MARKER in first_content:
        return _self_correction_rollback_response(turn, call_id)
    if turn == 0:
        return "", (ToolCallData(call_id, "list_repository", {"path": ""}),)
    if turn == 1:
        return "", (ToolCallData(call_id, "read_file", {"path": "README.md"}),)
    if turn == 2:
        index_html = _MOCK_INDEX_HTML
        if _is_rework(messages):
            index_html = index_html.replace(
                "<p>Built by the Engineer's tool loop.</p>",
                "<p>Built by the Engineer's tool loop.</p>\n    <p>Updated per CEO feedback.</p>",
            )
        return "", (
            ToolCallData(
                call_id,
                "apply_patch",
                {
                    "files": [
                        {"path": "index.html", "content": index_html},
                        {"path": "style.css", "content": _MOCK_STYLE_CSS},
                    ]
                },
            ),
        )
    if turn == 3:
        return "", (ToolCallData(call_id, "run_validation", {"profile": "python-syntax"}),)
    summary = (
        "Added a small static landing page (index.html, style.css) via the Agent "
        "Harness tool loop: listed the repository, read the README for context, "
        "applied the patch, then ran validation before finishing."
    )
    return f"**Change Summary:** {summary}", ()


class MockProvider(ProviderGateway):
    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        if opts.get("tools"):
            text, tool_calls = _tool_loop_response(messages)
            usage = _fabricate_usage(system, messages, text)
            return CompletionResult(
                text=text,
                model=model_ref,
                provider="mock",
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                tool_calls=tool_calls,
                stop_reason="tool_use" if tool_calls else "end_turn",
            )
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
