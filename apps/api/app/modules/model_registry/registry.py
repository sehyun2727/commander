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
    },
    "anthropic": {
        # Haiku for the fast planning/review passes, Sonnet for the
        # heavier build step. See docs/DECISIONS.md.
        "planner-default": "claude-haiku-4-5-20251001",
        "builder-default": "claude-sonnet-4-6",
        "reviewer-default": "claude-haiku-4-5-20251001",
    },
}

RECOMMENDED_PROVIDER = "mock"

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


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for one call. Unknown models price at $0 rather than
    raising — a missing price-table entry shouldn't fail a mission."""
    input_price, output_price = PRICE_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    return round(cost, 6)
