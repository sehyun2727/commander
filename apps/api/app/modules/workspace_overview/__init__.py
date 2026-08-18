"""CEO Workspace projection module (Sprint 13): a single read-only
snapshot endpoint over authoritative domain state, plus the deterministic
`next_action` policy, behind this package's public surface per Rule #1.
"""

from .routes import router

__all__ = ["router"]
