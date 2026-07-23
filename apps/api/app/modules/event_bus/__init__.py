"""Event Bus module — the foundation of Commander's event-driven design.

Implements core.interfaces.event_bus.EventBus. Every event in the system
is persisted here (`events` table) and dispatched to subscribers and any
live SSE listeners. Dependency floor of the backend: depends on nothing
else in the system besides core.events / core.db_models.
"""

from .bus import InProcessEventBus

__all__ = ["InProcessEventBus"]
