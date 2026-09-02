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
GUEST_TTL_DAYS_ENV = "ASTRO_ABM_GUEST_TTL_DAYS"
PASSWORD_HASH = PasswordHash.recommended()


class UsernameUnavailableError(ValueError):
    pass


class RegistrationRateLimitError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


@dataclass(frozen=True)
class SessionCredentials:
    session_token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class GuestCredentials:
    guest_id: str
    guest_token: str
    expires_at: datetime


@dataclass(frozen=True)
class ScenarioOwnership:
    scenario_id: str
    owner_type: str
    owner_id: str
    visibility: str


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

    def _connect(self, *, timeout_seconds: float = 5.0) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_path,
            timeout=max(0.01, timeout_seconds),
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            self._ensure_schema(connection)
        except Exception:
            connection.close()
            raise
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

            CREATE TABLE IF NOT EXISTS guest_workspaces (
                guest_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                claimed_by_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS scenario_ownership (
                scenario_id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL CHECK(owner_type IN ('guest', 'user', 'legacy')),
                owner_id TEXT NOT NULL,
                visibility TEXT NOT NULL CHECK(visibility IN ('public', 'private')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS operation_events (
                event_id TEXT PRIMARY KEY,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS generation_leases (
                lease_id TEXT PRIMARY KEY,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS scenario_ownership_owner_idx
                ON scenario_ownership(owner_type, owner_id);
            CREATE INDEX IF NOT EXISTS operation_events_lookup_idx
                ON operation_events(actor_type, actor_id, operation, created_at);
            CREATE INDEX IF NOT EXISTS generation_leases_expiry_idx
                ON generation_leases(expires_at);
            """
        )
        connection.commit()

    def register(
        self,
        *,
        username: str,
        password: str,
        display_name: str | None,
        hourly_limit: int | None = None,
    ) -> CurrentUser:
        now = _utc_now()
        user_id = str(uuid4())
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if hourly_limit is not None:
                    cutoff = _iso(now - timedelta(hours=1))
                    row = connection.execute(
                        "SELECT COUNT(*) AS count FROM users WHERE created_at >= ?",
                        (cutoff,),
                    ).fetchone()
                    if int(row["count"] if row else 0) >= max(1, hourly_limit):
                        raise RegistrationRateLimitError(
                            "global account registration rate limit reached"
                        )
                credential_hash = PASSWORD_HASH.hash(password)
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
                        credential_hash,
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

    def create_guest(self) -> GuestCredentials:
        now = _utc_now()
        try:
            ttl_days = max(1, min(365, int(os.getenv(GUEST_TTL_DAYS_ENV, "30"))))
        except ValueError:
            ttl_days = 30
        expires_at = now + timedelta(days=ttl_days)
        guest_id = str(uuid4())
        guest_token = secrets.token_urlsafe(48)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO guest_workspaces(guest_id, token_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (guest_id, _digest(guest_token), _iso(now), _iso(expires_at)),
            )
        return GuestCredentials(guest_id, guest_token, expires_at)

    def guest_id_for_token(self, guest_token: str | None) -> str | None:
        if not guest_token:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT guest_id FROM guest_workspaces
                WHERE token_hash = ? AND claimed_by_user_id IS NULL AND expires_at > ?
                """,
                (_digest(guest_token), _iso(_utc_now())),
            ).fetchone()
        return row["guest_id"] if row else None

    def set_scenario_ownership(
        self,
        *,
        scenario_id: str,
        owner_type: str,
        owner_id: str,
        visibility: str,
    ) -> None:
        now = _iso(_utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scenario_ownership(
                    scenario_id, owner_type, owner_id, visibility, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scenario_id) DO UPDATE SET
                    owner_type = excluded.owner_type,
                    owner_id = excluded.owner_id,
                    visibility = excluded.visibility,
                    updated_at = excluded.updated_at
                """,
                (scenario_id, owner_type, owner_id, visibility, now, now),
            )

    def get_scenario_ownership(self, scenario_id: str) -> ScenarioOwnership | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT scenario_id, owner_type, owner_id, visibility
                FROM scenario_ownership WHERE scenario_id = ?
                """,
                (scenario_id,),
            ).fetchone()
        return ScenarioOwnership(**dict(row)) if row else None

    def delete_scenario_ownership(self, scenario_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM scenario_ownership WHERE scenario_id = ?",
                (scenario_id,),
            )

    def claim_guest_scenarios(self, *, guest_token: str | None, user_id: str) -> int:
        guest_id = self.guest_id_for_token(guest_token)
        if guest_id is None:
            return 0
        now = _iso(_utc_now())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE scenario_ownership
                SET owner_type = 'user', owner_id = ?, updated_at = ?
                WHERE owner_type = 'guest' AND owner_id = ?
                """,
                (user_id, now, guest_id),
            )
            connection.execute(
                "UPDATE guest_workspaces SET claimed_by_user_id = ? WHERE guest_id = ?",
                (user_id, guest_id),
            )
        return max(0, cursor.rowcount)

    def count_owned_scenarios(self, *, owner_type: str, owner_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM scenario_ownership WHERE owner_type = ? AND owner_id = ?",
                (owner_type, owner_id),
            ).fetchone()
        return int(row["count"] if row else 0)

    def record_operation_if_allowed(
        self,
        *,
        actor_type: str,
        actor_id: str,
        operation: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        now = _utc_now()
        cutoff = _iso(now - timedelta(seconds=max(1, window_seconds)))
        try:
            with self._connect(timeout_seconds=_rate_limit_db_timeout()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS count FROM operation_events
                    WHERE actor_type = ? AND actor_id = ? AND operation = ? AND created_at >= ?
                    """,
                    (actor_type, actor_id, operation, cutoff),
                ).fetchone()
                if int(row["count"] if row else 0) >= max(1, limit):
                    return False
                connection.execute(
                    "INSERT INTO operation_events(event_id, actor_type, actor_id, operation, created_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid4()), actor_type, actor_id, operation, _iso(now)),
                )
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                return False
            raise
        return True

    def expired_guest_scenario_ids(self) -> list[str]:
        now = _iso(_utc_now())
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT ownership.scenario_id
                FROM scenario_ownership ownership
                JOIN guest_workspaces guest ON guest.guest_id = ownership.owner_id
                WHERE ownership.owner_type = 'guest'
                  AND guest.claimed_by_user_id IS NULL
                  AND guest.expires_at <= ?
                """,
                (now,),
            ).fetchall()
        return [str(row["scenario_id"]) for row in rows]

    def try_acquire_generation_lease(
        self,
        *,
        actor_type: str,
        actor_id: str,
        global_limit: int,
        actor_limit: int,
        lease_seconds: int,
    ) -> str | None:
        now = _utc_now()
        expires_at = now + timedelta(seconds=max(30, lease_seconds))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM generation_leases WHERE expires_at <= ?",
                (_iso(now),),
            )
            global_count = connection.execute(
                "SELECT COUNT(*) AS count FROM generation_leases"
            ).fetchone()["count"]
            actor_count = connection.execute(
                """
                SELECT COUNT(*) AS count FROM generation_leases
                WHERE actor_type = ? AND actor_id = ?
                """,
                (actor_type, actor_id),
            ).fetchone()["count"]
            if int(global_count) >= max(1, global_limit) or int(actor_count) >= max(1, actor_limit):
                return None
            lease_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO generation_leases(
                    lease_id, actor_type, actor_id, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (lease_id, actor_type, actor_id, _iso(now), _iso(expires_at)),
            )
        return lease_id

    def release_generation_lease(self, lease_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM generation_leases WHERE lease_id = ?", (lease_id,))

    def abuse_protection_status(self) -> dict[str, int]:
        now = _iso(_utc_now())
        with self._connect() as connection:
            operation_events = connection.execute(
                "SELECT COUNT(*) AS count FROM operation_events"
            ).fetchone()["count"]
            active_leases = connection.execute(
                "SELECT COUNT(*) AS count FROM generation_leases WHERE expires_at > ?",
                (now,),
            ).fetchone()["count"]
            active_guests = connection.execute(
                """
                SELECT COUNT(*) AS count FROM guest_workspaces
                WHERE claimed_by_user_id IS NULL AND expires_at > ?
                """,
                (now,),
            ).fetchone()["count"]
        return {
            "operation_events": int(operation_events),
            "active_generation_leases": int(active_leases),
            "active_guest_workspaces": int(active_guests),
        }

    def cleanup_operational_state(self, *, max_event_age_seconds: int = 172800) -> dict[str, int]:
        now = _utc_now()
        cutoff = _iso(now - timedelta(seconds=max(86400, max_event_age_seconds)))
        with self._connect() as connection:
            events = connection.execute(
                "DELETE FROM operation_events WHERE created_at < ?",
                (cutoff,),
            ).rowcount
            leases = connection.execute(
                "DELETE FROM generation_leases WHERE expires_at <= ?",
                (_iso(now),),
            ).rowcount
            sessions = connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL",
                (_iso(now),),
            ).rowcount
        return {
            "operation_events": max(0, events),
            "generation_leases": max(0, leases),
            "sessions": max(0, sessions),
        }

    def delete_expired_guests(self) -> int:
        now = _iso(_utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM scenario_ownership
                WHERE owner_type = 'guest' AND owner_id IN (
                    SELECT guest_id FROM guest_workspaces
                    WHERE claimed_by_user_id IS NULL AND expires_at <= ?
                )
                """,
                (now,),
            )
            cursor = connection.execute(
                "DELETE FROM guest_workspaces WHERE claimed_by_user_id IS NULL AND expires_at <= ?",
                (now,),
            )
        return max(0, cursor.rowcount)


def _rate_limit_db_timeout() -> float:
    try:
        configured = float(os.getenv("ASTRO_ABM_RATE_LIMIT_DB_TIMEOUT_SECONDS", "0.25"))
    except ValueError:
        configured = 0.25
    return max(0.01, min(5.0, configured))
