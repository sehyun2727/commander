"""Event Bus module — the foundation of Commander's event-driven design.

Will implement core.interfaces.event_bus.EventBus. Every event in the
system is persisted here and dispatched to subscribers. This module is the
dependency floor of the backend: it depends on nothing else in the system
(only on core.events contracts), specifically to make circular dependencies
impossible.

No implementation yet (Sprint 1 defines module boundaries only).
"""
