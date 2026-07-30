"""Local email+password identity provider (Sprint 9 §2.2, §2.3) -- the only
implementation this sprint ships. bcrypt directly, not passlib (unmaintained,
per brief). Cost factor 12; no password complexity rules beyond an 8-char
minimum enforced at the request-schema layer -- this is a local tool.
"""

from __future__ import annotations

import bcrypt
from sqlalchemy import select

from ....core.db_models import UserORM
from ..identity import IdentityProvider, UserIdentity

BCRYPT_COST = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class LocalIdentityProvider(IdentityProvider):
    provider_key = "local"

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def authenticate(self, credentials: dict) -> UserIdentity | None:
        email = credentials["email"].strip().lower()
        password = credentials["password"]
        async with self._session_factory() as session:
            result = await session.execute(select(UserORM).where(UserORM.email == email))
            user = result.scalars().first()
        if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
            return None
        return UserIdentity(provider_subject=None, email=user.email, display_name=user.display_name)
