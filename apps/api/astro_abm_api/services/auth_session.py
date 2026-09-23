from __future__ import annotations

import os
import secrets

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


def csrf_cookie_values(request: Request) -> list[str]:
    # Cookie parsers collapse duplicate names, which can hide the current host cookie.
    values: list[str] = []
    for cookie in request.headers.get("cookie", "").split(";"):
        name, separator, value = cookie.strip().partition("=")
        if separator and name == CSRF_COOKIE and value not in values:
            values.append(value)
    return values[:8]


def current_csrf_token(request: Request) -> str | None:
    session_token = request.cookies.get(SESSION_COOKIE)
    store = AuthStore()
    for value in csrf_cookie_values(request):
        if store.validate_csrf(session_token, value):
            return value
    return None


def require_csrf(request: Request) -> None:
    session_token = request.cookies.get(SESSION_COOKIE)
    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_header or not any(
        secrets.compare_digest(cookie, csrf_header)
        for cookie in csrf_cookie_values(request)
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    if not AuthStore().validate_csrf(session_token, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
