"""Model Registry module.

Catalogs every available model across providers, keyed by logical ref
("planner-default", "builder-default", "reviewer-default") so that
changing which model backs a role never requires an application code
change. Read by provider_gateway to resolve model -> provider routing.
"""

from .registry import MODEL_REGISTRY, RECOMMENDED_PROVIDER, resolve

__all__ = ["MODEL_REGISTRY", "RECOMMENDED_PROVIDER", "resolve"]
