from __future__ import annotations

import os

from fastapi import HTTPException, Request, Response

from astro_abm_api.models.auth import CurrentUser
from astro_abm_api.services.auth_store import AuthStore, GuestCredentials, SessionCredentials


SESSION_COOKIE = "astro_abm_session"
CSRF_COOKIE = "astro_abm_csrf"
GUEST_COOKIE = "astro_abm_guest"


def _production() -> bool:
    return os.getenv("ASTRO_ABM_ENV", "development").strip().lower() == "production"


def set_auth_cookies(response: Response, credentials: SessionCredentials) -> None:
    secure = _production()
    response.set_cookie(
        SESSION_COOKIE,
        credentials.session_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        expires=credentials.expires_at,
    )
    response.set_cookie(
        CSRF_COOKIE,
        credentials.csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        expires=credentials.expires_at,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def set_guest_cookie(response: Response, credentials: GuestCredentials) -> None:
    response.set_cookie(
        GUEST_COOKIE,
        credentials.guest_token,
        httponly=True,
        secure=_production(),
        samesite="lax",
        path="/",
        expires=credentials.expires_at,
    )


def guest_id(request: Request) -> str | None:
    return AuthStore().guest_id_for_token(request.cookies.get(GUEST_COOKIE))


def ensure_guest(request: Request, response: Response) -> str:
    existing = guest_id(request)
    if existing:
        return existing
    credentials = AuthStore().create_guest()
    set_guest_cookie(response, credentials)
    return credentials.guest_id


def current_user(request: Request) -> CurrentUser | None:
    return AuthStore().user_for_session(request.cookies.get(SESSION_COOKIE))


def require_current_user(request: Request) -> CurrentUser:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_csrf(request: Request) -> None:
    session_token = request.cookies.get(SESSION_COOKIE)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    if not AuthStore().validate_csrf(session_token, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
