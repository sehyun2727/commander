"""Agent Runtime module.

Will implement core.interfaces.agent_runtime.AgentRuntime. Hosts every
running agent (PM, Backend Engineer, Frontend Engineer, QA Engineer,
Reviewer, and future roles). Agents never call each other directly —
coordination happens only through events on the Event Bus.

Allowed dependencies: event_bus, workspace_manager, provider_gateway (all
via their interfaces in core.interfaces).

No implementation yet (Sprint 1 defines module boundaries only).
"""
