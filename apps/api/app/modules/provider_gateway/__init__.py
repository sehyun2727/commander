"""Provider Gateway module.

Will implement core.interfaces.provider_gateway.ProviderGateway. The only
module allowed to call AI provider APIs (OpenAI, Anthropic, Google,
OpenRouter, and future local models such as Ollama/LM Studio). Agents must
never call a provider SDK directly — only through this gateway.

Allowed dependencies: model_registry (to resolve model -> provider
routing), event_bus.

No implementation yet (Sprint 1 defines module boundaries only).
"""
