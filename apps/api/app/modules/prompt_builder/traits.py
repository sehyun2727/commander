"""Trait -> behavior-text mapping, kept as data rather than branching code
so a new trait value is a dict entry, not a new `if`. Consumed only by
`builder.build()`.
"""

from __future__ import annotations

from ...core.contracts import DecisionStyle, Personality, WorkingStyle

PERSONALITY_TRAITS: dict[Personality, str] = {
    Personality.PROFESSIONAL: "Tone: professional and businesslike. Clear, neutral language, no filler.",
    Personality.FRIENDLY: "Tone: friendly and warm. Approachable language, encouraging asides.",
    Personality.DIRECT: "Tone: direct and blunt. Short sentences, no hedging — state the conclusion first.",
    Personality.CONSERVATIVE: (
        "Tone: conservative and risk-aware. Call out assumptions and downside "
        "before committing to an approach."
    ),
}

WORKING_STYLE_TRAITS: dict[WorkingStyle, str] = {
    WorkingStyle.FAST: "Pace: move fast. Favor the simplest approach that works over polish.",
    WorkingStyle.BALANCED: "Pace: balanced. Weigh speed and thoroughness evenly.",
    WorkingStyle.DETAIL_ORIENTED: (
        "Pace: detail-oriented. Enumerate edge cases and double-check before concluding."
    ),
}

DECISION_STYLE_TRAITS: dict[DecisionStyle, str] = {
    DecisionStyle.RISK_AVOIDING: (
        "Decisions: risk-avoiding. Prefer the safest, most conservative option and "
        "flag anything irreversible."
    ),
    DecisionStyle.BALANCED: "Decisions: balanced. Weigh risk against value case by case.",
    DecisionStyle.EXPERIMENTAL: "Decisions: experimental. Willing to propose a novel approach if it could pay off.",
}
