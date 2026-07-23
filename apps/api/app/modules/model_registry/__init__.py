"""Model Registry module.

Catalogs every available model across providers, and which are
"recommended". Read by provider_gateway (to route requests) and by the API
layer (to list models for Dashboard settings). Changing available models
must never require a code change elsewhere in the system.

Allowed dependencies: event_bus (to publish model.changed).

No implementation yet (Sprint 1 defines module boundaries only).
"""
