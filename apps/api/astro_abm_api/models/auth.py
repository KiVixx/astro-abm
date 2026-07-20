from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class CurrentUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    username: str
    display_name: str | None
    created_at: datetime
    identity_providers: list[str]


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    user: CurrentUser | None
    csrf_token: str | None = None
    password_recovery_available: bool = False


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logged_out: bool
