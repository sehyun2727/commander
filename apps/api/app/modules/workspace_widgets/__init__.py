"""CEO Workspace widget system (Sprint 15).

Canonical, server-owned widget registry plus per-(user, company) layout
preferences -- presentation-only configuration over the existing Sprint 13
`WorkspaceSnapshot`, never a second source of business truth.
"""

from .registry import REQUIRED_WIDGET_KEYS, WIDGETS, WIDGETS_BY_KEY, WidgetDefinition
from .routes import router

__all__ = [
    "REQUIRED_WIDGET_KEYS",
    "WIDGETS",
    "WIDGETS_BY_KEY",
    "WidgetDefinition",
    "router",
]
