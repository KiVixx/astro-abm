from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from astro_abm_api.models.auth import (
    AuthSessionResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
)
from astro_abm_api.services.auth_session import (
    clear_auth_cookies,
    current_user,
    require_csrf,
    require_current_user,
    set_auth_cookies,
)
from astro_abm_api.services.auth_store import (
    AuthStore,
    InvalidCredentialsError,
    UsernameUnavailableError,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthSessionResponse, status_code=201)
def register(request: RegisterRequest, response: Response) -> AuthSessionResponse:
    store = AuthStore()
    try:
        user = store.register(
            username=request.username,
            password=request.password,
            display_name=request.display_name,
        )
    except UsernameUnavailableError as error:
        raise HTTPException(status_code=409, detail="account registration unavailable") from error
    credentials = store.create_session(user.user_id)
    set_auth_cookies(response, credentials)
    return AuthSessionResponse(authenticated=True, user=user, csrf_token=credentials.csrf_token)


@router.post("/login", response_model=AuthSessionResponse)
def login(request: LoginRequest, response: Response) -> AuthSessionResponse:
    store = AuthStore()
    try:
        user = store.authenticate(username=request.username, password=request.password)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="invalid username or password") from error
    credentials = store.create_session(user.user_id)
    set_auth_cookies(response, credentials)
    return AuthSessionResponse(authenticated=True, user=user, csrf_token=credentials.csrf_token)


@router.get("/me", response_model=AuthSessionResponse)
def me(request: Request) -> AuthSessionResponse:
    user = current_user(request)
    return AuthSessionResponse(authenticated=user is not None, user=user)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response) -> LogoutResponse:
    require_csrf(request)
    AuthStore().revoke_session(request.cookies.get("astro_abm_session"))
    clear_auth_cookies(response)
    return LogoutResponse(logged_out=True)


@router.post("/change-password", response_model=LogoutResponse)
def change_password(request: Request, payload: ChangePasswordRequest, response: Response) -> LogoutResponse:
    user = require_current_user(request)
    require_csrf(request)
    try:
        AuthStore().change_password(
            user_id=user.user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=401, detail="invalid username or password") from error
    clear_auth_cookies(response)
    return LogoutResponse(logged_out=True)
