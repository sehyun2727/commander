"""Model Registry module.

Catalogs every available model across providers, keyed by logical ref
("planner-default", "builder-default", "reviewer-default") so that
changing which model backs a role never requires an application code
change. Read by provider_gateway to resolve model -> provider routing.
"""

from .overrides import get_override
from .registry import (
    AVAILABLE_MODELS,
    MODEL_REGISTRY,
    PRICE_PER_MILLION_TOKENS,
    RECOMMENDED_PROVIDER,
    ROLES,
    cost_for,
    options_for_role,
    resolve,
)
from .routes import router

__all__ = [
    "AVAILABLE_MODELS",
    "MODEL_REGISTRY",
    "PRICE_PER_MILLION_TOKENS",
    "RECOMMENDED_PROVIDER",
    "ROLES",
    "cost_for",
    "get_override",
    "options_for_role",
    "resolve",
    "router",
]
