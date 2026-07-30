"""Auth module.

Owns authentication for the CEO Dashboard: local email+password accounts,
session issuance/verification/revocation. Used only by the API layer's
request handling (deps.get_current_user, routes.py) -- no other domain
module depends on it, and it depends on none of them.
"""

from .routes import router

__all__ = ["router"]
