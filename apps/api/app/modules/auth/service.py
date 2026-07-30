"""Register / login / session issue-verify-revoke (Sprint 9 §2.1-2.5).

Sessions are HttpOnly cookies, not JWT -- the `sessions` table is the
single source of truth for "is this session still valid," so revoking one
is a single row delete and nothing survives on a signed-out browser. Only
the SHA-256 hash of the session token is ever persisted (db_models.
SessionORM); the raw token exists only in the CEO's browser cookie.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ...core.db_models import SessionORM, UserORM
from .providers.local import LocalIdentityProvider, hash_password

SESSION_COOKIE_NAME = "commander_session"
SESSION_TOKEN_BYTES = 32
SESSION_MAX_AGE = timedelta(days=30)
SESSION_SLIDING_THRESHOLD = timedelta(days=7)

# Login failures never reveal which half was wrong -- account enumeration
# defense (brief §2.5). Always exactly this one sentence, Commander voice.
LOGIN_FAILURE_MESSAGE = "We couldn't sign you in with that email and password."


class EmailAlreadyRegisteredError(ValueError):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def register(session_factory, email: str, password: str, display_name: str) -> UserORM:
    email = _normalize_email(email)
    async with session_factory() as session:
        existing = await session.execute(select(UserORM).where(UserORM.email == email))
        if existing.scalars().first() is not None:
            raise EmailAlreadyRegisteredError(email)

        user = UserORM(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            auth_provider="local",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def authenticate_local(session_factory, email: str, password: str) -> UserORM | None:
    identity = await LocalIdentityProvider(session_factory).authenticate({"email": email, "password": password})
    if identity is None:
        return None
    async with session_factory() as session:
        result = await session.execute(select(UserORM).where(UserORM.email == identity.email))
        return result.scalars().first()


async def issue_session(session_factory, user_id: str) -> str:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        session.add(
            SessionORM(
                id=_hash_token(token),
                user_id=user_id,
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_MAX_AGE,
            )
        )
        user = await session.get(UserORM, user_id)
        user.last_login_at = now
        await session.commit()
    return token


async def resolve_session(session_factory, token: str) -> UserORM | None:
    """Look up the CEO behind a raw session token, sliding the expiry
    forward when it's within 7 days of expiring (§2.1). Returns None for a
    missing, expired, or unknown session -- callers always answer a plain
    401 and never distinguish why."""
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        row = await session.get(SessionORM, token_hash)
        if row is None:
            return None
        # SQLite round-trips DateTime(timezone=True) as naive (Postgres
        # doesn't) -- normalize before comparing, same pattern as
        # workflow_engine.engine's created_at handling.
        expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return None

        row.last_seen_at = now
        if expires_at - now < SESSION_SLIDING_THRESHOLD:
            row.expires_at = now + SESSION_MAX_AGE
        await session.commit()

        return await session.get(UserORM, row.user_id)


async def reset_password(session_factory, email: str, new_password: str) -> UserORM | None:
    """Admin-CLI-only password reset (§2.6) -- there is no self-service
    "forgot password" flow this sprint, so a locked-out CEO's only recourse
    is `scripts/reset_password.py` run against the server's own DB."""
    email = _normalize_email(email)
    async with session_factory() as session:
        result = await session.execute(select(UserORM).where(UserORM.email == email))
        user = result.scalars().first()
        if user is None:
            return None
        user.password_hash = hash_password(new_password)
        await session.commit()
        await session.refresh(user)
        return user


async def revoke_session(session_factory, token: str) -> None:
    token_hash = _hash_token(token)
    async with session_factory() as session:
        row = await session.get(SessionORM, token_hash)
        if row is not None:
            await session.delete(row)
            await session.commit()
