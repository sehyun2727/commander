"""Timeline module.

Company conversation feed for the CEO — not chat, not logs. Read-only: it
exposes cursor-paginated event history via the Event Bus's `page()` method
and never publishes.
"""

from .routes import router

__all__ = ["router"]
