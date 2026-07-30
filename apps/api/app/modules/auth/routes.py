from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ...core.config import settings
from ...core.db_models import UserORM
from ...deps import get_current_user, get_session_factory
from . import service
from .schemas import LoginRequest, RegisterRequest, UserResponse
from .service import EmailAlreadyRegisteredError

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days, matches service.SESSION_MAX_AGE


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        service.SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.commander_cookie_secure,
    )


@router.post("/register", response_model=UserResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    session_factory=Depends(get_session_factory),
):
    try:
        user = await service.register(session_factory, body.email, body.password, body.display_name)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    token = await service.issue_session(session_factory, user.id)
    _set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session_factory=Depends(get_session_factory),
):
    user = await service.authenticate_local(session_factory, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail=service.LOGIN_FAILURE_MESSAGE)

    token = await service.issue_session(session_factory, user.id)
    _set_session_cookie(response, token)
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user: UserORM = Depends(get_current_user),
    session_factory=Depends(get_session_factory),
):
    token = request.cookies.get(service.SESSION_COOKIE_NAME)
    if token:
        await service.revoke_session(session_factory, token)
    response.delete_cookie(service.SESSION_COOKIE_NAME)
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(user: UserORM = Depends(get_current_user)):
    return user
