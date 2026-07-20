from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pwdlib import PasswordHash

from astro_abm_api.models.auth import CurrentUser
from astro_abm_api.services.scenario_store import repo_root


ACCOUNTS_DB_PATH_ENV = "ASTRO_ABM_ACCOUNTS_DB_PATH"
SESSION_TTL_HOURS_ENV = "ASTRO_ABM_SESSION_TTL_HOURS"
PASSWORD_HASH = PasswordHash.recommended()


class UsernameUnavailableError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


@dataclass(frozen=True)
class SessionCredentials:
    session_token: str
    csrf_token: str
    expires_at: datetime


def default_accounts_db_path() -> Path:
    configured = os.getenv(ACCOUNTS_DB_PATH_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return repo_root() / ".local" / "astro_abm_accounts.sqlite3"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthStore:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = (
            Path(database_path).expanduser().resolve()
            if database_path
            else default_accounts_db_path()
        )

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        self._ensure_schema(connection)
        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_identities (
                identity_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                subject TEXT NOT NULL,
                credential_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(provider, subject)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                session_hash TEXT NOT NULL UNIQUE,
                csrf_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            );

            CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);
            """
        )
        connection.commit()

    def register(
        self,
        *,
        username: str,
        password: str,
        display_name: str | None,
    ) -> CurrentUser:
        now = _utc_now()
        user_id = str(uuid4())
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO users(user_id, display_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, display_name, _iso(now), _iso(now)),
                )
                connection.execute(
                    """
                    INSERT INTO auth_identities(
                        identity_id, user_id, provider, subject, credential_hash, created_at, updated_at
                    ) VALUES (?, ?, 'password', ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        user_id,
                        username.lower(),
                        PASSWORD_HASH.hash(password),
                        _iso(now),
                        _iso(now),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise UsernameUnavailableError("username is unavailable") from error
        user = self.get_user(user_id)
        assert user is not None
        return user

    def authenticate(self, *, username: str, password: str) -> CurrentUser:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT i.user_id, i.credential_hash
                FROM auth_identities i
                WHERE i.provider = 'password' AND i.subject = ?
                """,
                (username.strip().lower(),),
            ).fetchone()
        if row is None or not row["credential_hash"]:
            raise InvalidCredentialsError("invalid username or password")
        if not PASSWORD_HASH.verify(password, row["credential_hash"]):
            raise InvalidCredentialsError("invalid username or password")
        user = self.get_user(row["user_id"])
        if user is None:
            raise InvalidCredentialsError("invalid username or password")
        return user

    def get_user(self, user_id: str) -> CurrentUser | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, display_name, created_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            identities = connection.execute(
                "SELECT provider, subject FROM auth_identities WHERE user_id = ? ORDER BY provider",
                (user_id,),
            ).fetchall()
        username = next(
            (item["subject"] for item in identities if item["provider"] == "password"),
            "",
        )
        return CurrentUser(
            user_id=row["user_id"],
            username=username,
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            identity_providers=sorted({item["provider"] for item in identities}),
        )

    def create_session(self, user_id: str) -> SessionCredentials:
        now = _utc_now()
        try:
            ttl_hours = max(1, min(24 * 30, int(os.getenv(SESSION_TTL_HOURS_ENV, "168"))))
        except ValueError:
            ttl_hours = 168
        expires_at = now + timedelta(hours=ttl_hours)
        session_token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    session_id, user_id, session_hash, csrf_hash, created_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(uuid4()),
                    user_id,
                    _digest(session_token),
                    _digest(csrf_token),
                    _iso(now),
                    _iso(expires_at),
                ),
            )
        return SessionCredentials(session_token, csrf_token, expires_at)

    def user_for_session(self, session_token: str | None) -> CurrentUser | None:
        if not session_token:
            return None
        now = _iso(_utc_now())
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT user_id FROM sessions
                WHERE session_hash = ? AND revoked_at IS NULL AND expires_at > ?
                """,
                (_digest(session_token), now),
            ).fetchone()
        return self.get_user(row["user_id"]) if row else None

    def validate_csrf(self, session_token: str | None, csrf_token: str | None) -> bool:
        if not session_token or not csrf_token:
            return False
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT csrf_hash FROM sessions
                WHERE session_hash = ? AND revoked_at IS NULL AND expires_at > ?
                """,
                (_digest(session_token), _iso(_utc_now())),
            ).fetchone()
        return bool(row and secrets.compare_digest(row["csrf_hash"], _digest(csrf_token)))

    def revoke_session(self, session_token: str | None) -> None:
        if not session_token:
            return
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE session_hash = ?",
                (_iso(_utc_now()), _digest(session_token)),
            )

    def change_password(
        self,
        *,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        user = self.get_user(user_id)
        if user is None:
            raise InvalidCredentialsError("invalid username or password")
        self.authenticate(username=user.username, password=current_password)
        now = _iso(_utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE auth_identities SET credential_hash = ?, updated_at = ?
                WHERE user_id = ? AND provider = 'password'
                """,
                (PASSWORD_HASH.hash(new_password), now, user_id),
            )
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ?",
                (now, user_id),
            )
