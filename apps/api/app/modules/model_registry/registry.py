"""Logical model refs -> concrete provider model ids.

Callers (workflow_engine) ask for a logical ref ("planner-default"), never
a hardcoded model id — swapping the underlying model is a registry edit,
not a code change, per docs/ARCHITECTURE.md § Model Registry.
"""

from __future__ import annotations

MODEL_REGISTRY: dict[str, dict[str, str]] = {
    "mock": {
        "planner-default": "mock-planner-v1",
        "builder-default": "mock-builder-v1",
        "reviewer-default": "mock-reviewer-v1",
        # Daily Report summarization and the Situation Report one-liner —
        # not pipeline roles, so neither is in ROLES/options_for_role and
        # the CEO can't reassign them.
        "reporter-default": "mock-reporter-v1",
        "situation-default": "mock-situation-v1",
    },
    "anthropic": {
        # Haiku for the fast planning/review passes, Sonnet for the
        # heavier build step. See docs/DECISIONS.md.
        "planner-default": "claude-haiku-4-5-20251001",
        "builder-default": "claude-sonnet-4-6",
        "reviewer-default": "claude-haiku-4-5-20251001",
        "reporter-default": "claude-haiku-4-5-20251001",
        "situation-default": "claude-haiku-4-5-20251001",
    },
}

RECOMMENDED_PROVIDER = "mock"

ROLES = ("planner", "builder", "reviewer")

# Every concrete model a provider exposes, independent of which role
# defaults to which — the CEO may reassign any of these to any role for
# that provider (see options_for_role for the one exception).
AVAILABLE_MODELS: dict[str, list[str]] = {
    "mock": ["mock-planner-v1", "mock-builder-v1", "mock-reviewer-v1"],
    "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
}

# Illustrative USD per-million-token prices, (input, output). Approximate by
# design (see docs/DECISIONS.md) — this is Payroll math for a CEO dashboard,
# not a billing system. Mock models get "play money" prices so Payroll is
# nonzero in mock mode with zero API keys; Anthropic prices are ballpark
# figures for the concrete models above.
PRICE_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "mock-planner-v1": (0.25, 1.25),
    "mock-builder-v1": (3.00, 15.00),
    "mock-reviewer-v1": (0.25, 1.25),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}


def resolve(provider: str, model_ref: str) -> str:
    try:
        return MODEL_REGISTRY[provider][model_ref]
    except KeyError as exc:
        raise ValueError(f"no model registered for provider={provider!r} ref={model_ref!r}") from exc


def options_for_role(provider: str, role: str) -> list[str]:
    """Which concrete models the CEO may pick for this role.

    Mock's role output is templated by a substring match on the model id
    (see mock_provider._role_from_ref) — reassigning "mock-planner-v1" onto
    the Reviewer role would silently produce planner-shaped text instead of
    an auditable Verdict line, breaking the pipeline's outcome parsing. Mock
    therefore offers no real choice, only its own fixed model per role.
    Anthropic's models are general-purpose, so any of them is valid for any
    role — swapping just trades cost/speed for quality."""
    if provider == "mock":
        return [resolve(provider, f"{role}-default")]
    return list(AVAILABLE_MODELS.get(provider, []))


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for one call. Unknown models price at $0 rather than
    raising — a missing price-table entry shouldn't fail a mission."""
    input_price, output_price = PRICE_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    return round(cost, 6)
