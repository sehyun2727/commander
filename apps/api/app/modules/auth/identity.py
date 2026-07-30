"""Identity abstraction (Sprint 9 §2.3).

One implementation per auth method. Adding Google OAuth later means adding
`providers/google.py` that implements this interface -- routes.py and the
session logic in service.py should not need to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class UserIdentity:
    """What a successful `authenticate()` hands back -- enough to find the
    matching `users` row, nothing more."""

    provider_subject: str | None
    email: str
    display_name: str


class IdentityProvider(ABC):
    provider_key: str

    @abstractmethod
    async def authenticate(self, credentials: dict) -> UserIdentity | None:
        """Return the identity for valid credentials, or None if invalid."""
