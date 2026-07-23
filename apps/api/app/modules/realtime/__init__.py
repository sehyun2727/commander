"""Realtime module: Server-Sent Events fan-out for the Timeline.

New in Sprint 3 (not in the Sprint 1/2 module list — SSE wasn't decided
until this sprint's brief). Depends only on event_bus's stream registry.
"""

from .routes import router

__all__ = ["router"]
