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


def resolve(provider: str, model_ref: str) -> str:
    try:
        return MODEL_REGISTRY[provider][model_ref]
    except KeyError as exc:
        raise ValueError(f"no model registered for provider={provider!r} ref={model_ref!r}") from exc
