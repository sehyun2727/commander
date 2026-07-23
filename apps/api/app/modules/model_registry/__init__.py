"""Model Registry module.

Catalogs every available model across providers, keyed by logical ref
("planner-default", "builder-default", "reviewer-default") so that
changing which model backs a role never requires an application code
change. Read by provider_gateway to resolve model -> provider routing.
"""

from .registry import MODEL_REGISTRY, PRICE_PER_MILLION_TOKENS, RECOMMENDED_PROVIDER, cost_for, resolve

__all__ = ["MODEL_REGISTRY", "PRICE_PER_MILLION_TOKENS", "RECOMMENDED_PROVIDER", "cost_for", "resolve"]
