from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote
from uuid import uuid4

import pandas as pd
import requests


MARKET_SERIES_DB_PATH_ENV = "ASTRO_ABM_MARKET_SERIES_DB_PATH"
MARKET_SERIES_DATA_ROOT_ENV = "ASTRO_ABM_MARKET_SERIES_DATA_ROOT"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=_-]{0,19}$")
ALLOWED_PROVIDERS = {"yahoo"}
FAILURE_PAUSE_THRESHOLD = 3


class MarketSeriesError(RuntimeError):
    pass


class MarketSeriesNotFoundError(MarketSeriesError):
    pass


class MarketSeriesConflictError(MarketSeriesError):
    pass


class MarketSeriesValidationError(MarketSeriesError):
    pass


@dataclass(frozen=True)
class MarketSeriesRecord:
    series_id: str
    symbol: str
    label: str
    asset_type: str
    provider: str
    provider_symbol: str
    currency: str
    market_timezone: str
    frequency: str
    status: str
    coverage_start: str | None
    coverage_end: str | None
    latest_observation_date: str | None
    last_attempt_at: str | None
    last_success_at: str | None
    consecutive_failures: int
    row_count: int
    data_path: str
    source_note: str
    license_note: str
    redistribution_allowed: bool
    error_message: str | None
    created_at: str
    updated_at: str
    owner_id: str
    visibility: str
    enabled: bool
    maintenance_enabled: bool
    is_owner: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketSeriesRefreshResult:
    series_id: str
    status: str
    fetched_rows: int
    rows_written: int
    coverage_start: str | None
    coverage_end: str | None
    latest_observation_date: str | None
    data_path: str
    attempts: int
    adopted_existing: bool = False
    errors: tuple[str, ...] = ()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_market_series_data_root() -> Path:
    configured = os.getenv(MARKET_SERIES_DATA_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return repo_root() / "astro_research" / "data" / "local"


def default_market_series_db_path() -> Path:
    configured = os.getenv(MARKET_SERIES_DB_PATH_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return default_market_series_data_root() / "market_series" / "registry.sqlite3"


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise MarketSeriesValidationError(
            "symbol must contain only letters, numbers, dot, dash, underscore, equals, or caret"
        )
    return symbol


class MarketSeriesStore:
    def __init__(
        self,
        database_path: str | Path | None = None,
        data_root: str | Path | None = None,
    ) -> None:
        self.database_path = (
            Path(database_path).expanduser().resolve()
            if database_path
            else default_market_series_db_path()
        )
        self.data_root = (
            Path(data_root).expanduser().resolve()
            if data_root
            else default_market_series_data_root()
        )

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_series (
                series_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                label TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_symbol TEXT NOT NULL,
                currency TEXT NOT NULL,
                market_timezone TEXT NOT NULL,
                frequency TEXT NOT NULL,
                status TEXT NOT NULL,
                coverage_start TEXT,
                coverage_end TEXT,
                latest_observation_date TEXT,
                last_attempt_at TEXT,
                last_success_at TEXT,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                row_count INTEGER NOT NULL DEFAULT 0,
                data_path TEXT NOT NULL,
                source_note TEXT NOT NULL,
                license_note TEXT NOT NULL,
                redistribution_allowed INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(provider, provider_symbol)
            );

            CREATE TABLE IF NOT EXISTS market_series_subscriptions (
                series_id TEXT NOT NULL REFERENCES market_series(series_id) ON DELETE CASCADE,
                owner_id TEXT NOT NULL,
                visibility TEXT NOT NULL CHECK(visibility IN ('public', 'private')),
                enabled INTEGER NOT NULL DEFAULT 1,
                maintenance_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(series_id, owner_id)
            );

            CREATE INDEX IF NOT EXISTS market_series_subscription_owner_idx
                ON market_series_subscriptions(owner_id);
            CREATE INDEX IF NOT EXISTS market_series_maintenance_idx
                ON market_series(status, consecutive_failures);
            """
        )
        return connection

    def register(
        self,
        *,
        owner_id: str,
        symbol: str,
        label: str,
        asset_type: str,
        provider: str,
        provider_symbol: str | None,
        currency: str,
        market_timezone: str,
        visibility: str,
        maintenance_enabled: bool,
    ) -> MarketSeriesRecord:
        provider_value = provider.strip().lower()
        if provider_value not in ALLOWED_PROVIDERS:
            raise MarketSeriesValidationError("unsupported market series provider")
        symbol_value = normalize_symbol(symbol)
        provider_symbol_value = normalize_symbol(provider_symbol or symbol_value)
        if visibility not in {"public", "private"}:
            raise MarketSeriesValidationError("invalid visibility")
        now = _iso_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT series_id FROM market_series WHERE provider = ? AND provider_symbol = ?",
                (provider_value, provider_symbol_value),
            ).fetchone()
            if row:
                series_id = str(row["series_id"])
            else:
                series_id = _series_id(provider_value, provider_symbol_value)
                data_path = self._relative_data_path(
                    symbol=symbol_value,
                    provider=provider_value,
                    series_id=series_id,
                )
                connection.execute(
                    """
                    INSERT INTO market_series(
                        series_id, symbol, label, asset_type, provider, provider_symbol,
                        currency, market_timezone, frequency, status, data_path,
                        source_note, license_note, redistribution_allowed,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'daily', 'pending_validation', ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        series_id,
                        symbol_value,
                        label.strip() or symbol_value,
                        asset_type.strip() or "equity",
                        provider_value,
                        provider_symbol_value,
                        currency.strip().upper() or "USD",
                        market_timezone.strip() or "America/New_York",
                        data_path,
                        "Yahoo chart daily data; local research use only.",
                        "Yahoo-derived local research data; licensing review required before redistribution.",
                        now,
                        now,
                    ),
                )
            existing = connection.execute(
                """
                SELECT 1 FROM market_series_subscriptions
                WHERE series_id = ? AND owner_id = ?
                """,
                (series_id, owner_id),
            ).fetchone()
            if existing:
                raise MarketSeriesConflictError("market series is already registered")
            connection.execute(
                """
                INSERT INTO market_series_subscriptions(
                    series_id, owner_id, visibility, enabled, maintenance_enabled,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    series_id,
                    owner_id,
                    visibility,
                    int(maintenance_enabled),
                    now,
                    now,
                ),
            )
        self.adopt_existing_if_available(series_id)
        return self.get_for_owner(series_id, owner_id)

    def list_visible(self, owner_id: str | None) -> list[MarketSeriesRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT series.*, subscription.owner_id, subscription.visibility,
                       subscription.enabled, subscription.maintenance_enabled
                FROM market_series series
                JOIN market_series_subscriptions subscription USING(series_id)
                WHERE subscription.visibility = 'public' OR subscription.owner_id = ?
                ORDER BY series.symbol, subscription.owner_id
                """,
                (owner_id or "",),
            ).fetchall()
        selected: dict[str, MarketSeriesRecord] = {}
        for row in rows:
            record = _record(row, owner_id=owner_id)
            current = selected.get(record.series_id)
            if current is None or record.is_owner:
                selected[record.series_id] = record
        return sorted(selected.values(), key=lambda item: item.symbol)

    def list_active(self, owner_id: str | None) -> list[MarketSeriesRecord]:
        return [
            item
            for item in self.list_visible(owner_id)
            if item.enabled and item.status == "active"
        ]

    def list_for_maintenance(self) -> list[MarketSeriesRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT series.*, MIN(subscription.owner_id) AS owner_id,
                       'private' AS visibility, 1 AS enabled, 1 AS maintenance_enabled
                FROM market_series series
                JOIN market_series_subscriptions subscription USING(series_id)
                WHERE subscription.enabled = 1
                  AND subscription.maintenance_enabled = 1
                  AND series.consecutive_failures < ?
                GROUP BY series.series_id
                ORDER BY series.symbol
                """,
                (FAILURE_PAUSE_THRESHOLD,),
            ).fetchall()
        return [_record(row, owner_id=None) for row in rows]

    def list_all_active(self) -> list[MarketSeriesRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT series.*, MIN(subscription.owner_id) AS owner_id,
                       'private' AS visibility, 1 AS enabled,
                       MAX(subscription.maintenance_enabled) AS maintenance_enabled
                FROM market_series series
                JOIN market_series_subscriptions subscription USING(series_id)
                WHERE subscription.enabled = 1 AND series.status = 'active'
                GROUP BY series.series_id
                ORDER BY series.symbol
                """
            ).fetchall()
        return [_record(row, owner_id=None) for row in rows]

    def get(self, series_id: str) -> MarketSeriesRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT series.*, MIN(subscription.owner_id) AS owner_id,
                       'private' AS visibility,
                       MAX(subscription.enabled) AS enabled,
                       MAX(subscription.maintenance_enabled) AS maintenance_enabled
                FROM market_series series
                JOIN market_series_subscriptions subscription USING(series_id)
                WHERE series.series_id = ?
                GROUP BY series.series_id
                """,
                (series_id,),
            ).fetchone()
        if row is None:
            raise MarketSeriesNotFoundError("market series not found")
        return _record(row, owner_id=None)

    def get_for_owner(self, series_id: str, owner_id: str) -> MarketSeriesRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT series.*, subscription.owner_id, subscription.visibility,
                       subscription.enabled, subscription.maintenance_enabled
                FROM market_series series
                JOIN market_series_subscriptions subscription USING(series_id)
                WHERE series.series_id = ? AND subscription.owner_id = ?
                """,
                (series_id, owner_id),
            ).fetchone()
        if row is None:
            raise MarketSeriesNotFoundError("market series not found")
        return _record(row, owner_id=owner_id)

    def update_subscription(
        self,
        series_id: str,
        owner_id: str,
        *,
        enabled: bool | None = None,
        maintenance_enabled: bool | None = None,
        visibility: str | None = None,
    ) -> MarketSeriesRecord:
        self.get_for_owner(series_id, owner_id)
        if visibility is not None and visibility not in {"public", "private"}:
            raise MarketSeriesValidationError("invalid visibility")
        now = _iso_now()
        with self._connect() as connection:
            fields: list[str] = ["updated_at = ?"]
            values: list[Any] = [now]
            if enabled is not None:
                fields.append("enabled = ?")
                values.append(int(enabled))
            if maintenance_enabled is not None:
                fields.append("maintenance_enabled = ?")
                values.append(int(maintenance_enabled))
            if visibility is not None:
                fields.append("visibility = ?")
                values.append(visibility)
            values.extend([series_id, owner_id])
            connection.execute(
                f"UPDATE market_series_subscriptions SET {', '.join(fields)} "
                "WHERE series_id = ? AND owner_id = ?",
                values,
            )
        return self.get_for_owner(series_id, owner_id)

    def delete_subscription(self, series_id: str, owner_id: str) -> None:
        self.get_for_owner(series_id, owner_id)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM market_series_subscriptions WHERE series_id = ? AND owner_id = ?",
                (series_id, owner_id),
            )

    def data_path(self, record: MarketSeriesRecord) -> Path:
        candidate = (self.data_root / record.data_path).resolve()
        root = self.data_root.resolve()
        if candidate != root and root not in candidate.parents:
            raise MarketSeriesValidationError("market series data path escaped local data root")
        return candidate

    def adopt_existing_if_available(self, series_id: str) -> bool:
        record = self.get(series_id)
        path = self.data_path(record)
        if not path.exists():
            return False
        frame = _read_and_validate_price_csv(path)
        self.record_success(record.series_id, frame, attempted_at=_iso_now())
        return True

    def record_attempt(self, series_id: str) -> str:
        attempted_at = _iso_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE market_series SET last_attempt_at = ?, updated_at = ? WHERE series_id = ?",
                (attempted_at, attempted_at, series_id),
            )
        return attempted_at

    def record_success(
        self,
        series_id: str,
        frame: pd.DataFrame,
        *,
        attempted_at: str,
    ) -> None:
        now = _iso_now()
        coverage_start, coverage_end = _coverage(frame)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE market_series SET
                    status = 'active', coverage_start = ?, coverage_end = ?,
                    latest_observation_date = ?, last_attempt_at = ?,
                    last_success_at = ?, consecutive_failures = 0,
                    row_count = ?, error_message = NULL, updated_at = ?
                WHERE series_id = ?
                """,
                (
                    coverage_start,
                    coverage_end,
                    coverage_end,
                    attempted_at,
                    now,
                    len(frame),
                    now,
                    series_id,
                ),
            )

    def record_failure(self, series_id: str, error: Exception, *, attempted_at: str) -> None:
        now = _iso_now()
        message = f"{type(error).__name__}: {str(error)[:500]}"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT consecutive_failures FROM market_series WHERE series_id = ?",
                (series_id,),
            ).fetchone()
            if row is None:
                raise MarketSeriesNotFoundError("market series not found")
            failures = int(row["consecutive_failures"]) + 1
            status = (
                "maintenance_failed"
                if failures >= FAILURE_PAUSE_THRESHOLD
                else "unavailable"
            )
            connection.execute(
                """
                UPDATE market_series SET status = ?, last_attempt_at = ?,
                    consecutive_failures = ?, error_message = ?, updated_at = ?
                WHERE series_id = ?
                """,
                (status, attempted_at, failures, message, now, series_id),
            )

    def _relative_data_path(
        self,
        *,
        symbol: str,
        provider: str,
        series_id: str,
    ) -> str:
        adopted = {
            ("yahoo", "TSLA"): Path("equity/tsla_daily.csv"),
        }.get((provider, symbol))
        if adopted and (self.data_root / adopted).exists():
            return adopted.as_posix()
        safe_symbol = re.sub(r"[^a-z0-9]+", "_", symbol.lower()).strip("_")
        return (
            Path("market_series")
            / provider
            / f"{safe_symbol}_{series_id[-8:]}_daily.csv"
        ).as_posix()


def refresh_market_series(
    store: MarketSeriesStore,
    series_id: str,
    *,
    end: date | None = None,
    attempts: int = 1,
    retry_delay_seconds: float = 0,
    session: requests.Session | None = None,
) -> MarketSeriesRefreshResult:
    record = store.get(series_id)
    path = store.data_path(record)
    attempted_at = store.record_attempt(series_id)
    errors: list[str] = []
    end_date = end or date.today()
    for attempt in range(1, max(1, min(3, attempts)) + 1):
        try:
            existing = (
                _read_and_validate_price_csv(path)
                if path.exists()
                else pd.DataFrame(columns=_price_columns())
            )
            start_date = _incremental_start(existing)
            fetched = _fetch_yahoo_daily(
                record.provider_symbol,
                start=start_date,
                end=end_date,
                session=session,
            )
            combined = _merge_price_frames(existing, fetched)
            _atomic_write_csv(combined, path)
            store.record_success(series_id, combined, attempted_at=attempted_at)
            coverage_start, coverage_end = _coverage(combined)
            return MarketSeriesRefreshResult(
                series_id=series_id,
                status="active",
                fetched_rows=len(fetched),
                rows_written=len(combined),
                coverage_start=coverage_start,
                coverage_end=coverage_end,
                latest_observation_date=coverage_end,
                data_path=str(path),
                attempts=attempt,
                errors=tuple(errors),
            )
        except Exception as error:
            errors.append(f"{type(error).__name__}: {str(error)[:500]}")
            if attempt < attempts and retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)
    failure = MarketSeriesValidationError(errors[-1] if errors else "market series refresh failed")
    store.record_failure(series_id, failure, attempted_at=attempted_at)
    current = store.get(series_id)
    return MarketSeriesRefreshResult(
        series_id=series_id,
        status=current.status,
        fetched_rows=0,
        rows_written=current.row_count,
        coverage_start=current.coverage_start,
        coverage_end=current.coverage_end,
        latest_observation_date=current.latest_observation_date,
        data_path=str(path),
        attempts=max(1, min(3, attempts)),
        errors=tuple(errors),
    )


def run_custom_market_series_maintenance(
    *,
    store: MarketSeriesStore | None = None,
    end: date | None = None,
    attempts: int = 3,
    retry_delay_seconds: float = 2,
) -> tuple[MarketSeriesRefreshResult, ...]:
    registry = store or MarketSeriesStore()
    results: list[MarketSeriesRefreshResult] = []
    for record in registry.list_for_maintenance():
        results.append(
            refresh_market_series(
                registry,
                record.series_id,
                end=end,
                attempts=attempts,
                retry_delay_seconds=retry_delay_seconds,
            )
        )
    return tuple(results)


def _fetch_yahoo_daily(
    symbol: str,
    *,
    start: date,
    end: date,
    session: requests.Session | None,
) -> pd.DataFrame:
    client = session or requests.Session()
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=UTC).timestamp())
    period2 = int(
        datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC).timestamp()
    )
    response = client.get(
        YAHOO_CHART_URL.format(symbol=quote(symbol, safe="")),
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=max(5, min(120, int(os.getenv("ASTRO_ABM_MARKET_FETCH_TIMEOUT_SECONDS", "30")))),
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result") or []
    if not result:
        detail = payload.get("chart", {}).get("error") or "empty Yahoo chart response"
        raise MarketSeriesValidationError(f"Yahoo symbol validation failed: {detail}")
    chart = result[0]
    timestamps = chart.get("timestamp") or []
    quote_rows = (chart.get("indicators", {}).get("quote") or [{}])[0]
    adjusted_rows = (chart.get("indicators", {}).get("adjclose") or [{}])[0]
    rows: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        row_date = pd.Timestamp(timestamp, unit="s", tz="UTC").date()
        if row_date < start or row_date > end:
            continue
        close = _list_get(quote_rows.get("close"), index)
        adjusted = _list_get(adjusted_rows.get("adjclose"), index, close)
        if close is None and adjusted is None:
            continue
        close_value = float(close if close is not None else adjusted)
        rows.append(
            {
                "date": row_date.isoformat(),
                "open": _list_get(quote_rows.get("open"), index, close_value),
                "high": _list_get(quote_rows.get("high"), index, close_value),
                "low": _list_get(quote_rows.get("low"), index, close_value),
                "close": close_value,
                "adj_close": _list_get(adjusted_rows.get("adjclose"), index, close_value),
                "volume": _list_get(quote_rows.get("volume"), index, 0) or 0,
            }
        )
    if not rows:
        raise MarketSeriesValidationError("Yahoo returned no daily observations")
    return _validate_price_frame(pd.DataFrame(rows))


def _read_and_validate_price_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        if "ts" not in frame.columns:
            raise MarketSeriesValidationError("price CSV must contain date or ts")
        frame = frame.rename(columns={"ts": "date"})
    return _validate_price_frame(frame)


def _validate_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    required = {"date", "close"}
    if not required.issubset(working.columns):
        raise MarketSeriesValidationError("price data must contain date and close")
    working["date"] = pd.to_datetime(working["date"], utc=True, errors="coerce").dt.date
    for column in ("open", "high", "low", "close", "adj_close", "volume"):
        if column not in working.columns:
            working[column] = working["close"] if column != "volume" else 0
        working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=["date", "close"])
    if working.empty:
        raise MarketSeriesValidationError("price data contains no valid observations")
    if working["date"].duplicated().any():
        raise MarketSeriesValidationError("price data contains duplicate dates")
    if (working[["open", "high", "low", "close", "adj_close"]] <= 0).any().any():
        raise MarketSeriesValidationError("price data contains non-positive prices")
    working = working.sort_values("date")
    working["date"] = working["date"].map(date.isoformat)
    return working[_price_columns()].reset_index(drop=True)


def _merge_price_frames(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return _validate_price_frame(fetched)
    combined = pd.concat([existing, fetched], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    return _validate_price_frame(combined)


def _atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        frame.to_csv(temporary, index=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _incremental_start(existing: pd.DataFrame) -> date:
    if existing.empty:
        configured = os.getenv("ASTRO_ABM_MARKET_SERIES_DEFAULT_START", "1970-01-01")
        return date.fromisoformat(configured)
    latest = pd.to_datetime(existing["date"], errors="coerce").max().date()
    return latest - timedelta(days=7)


def _coverage(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    if frame.empty:
        return None, None
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().date().isoformat(), dates.max().date().isoformat()


def _record(row: sqlite3.Row, *, owner_id: str | None) -> MarketSeriesRecord:
    values = dict(row)
    return MarketSeriesRecord(
        series_id=str(values["series_id"]),
        symbol=str(values["symbol"]),
        label=str(values["label"]),
        asset_type=str(values["asset_type"]),
        provider=str(values["provider"]),
        provider_symbol=str(values["provider_symbol"]),
        currency=str(values["currency"]),
        market_timezone=str(values["market_timezone"]),
        frequency=str(values["frequency"]),
        status=str(values["status"]),
        coverage_start=values["coverage_start"],
        coverage_end=values["coverage_end"],
        latest_observation_date=values["latest_observation_date"],
        last_attempt_at=values["last_attempt_at"],
        last_success_at=values["last_success_at"],
        consecutive_failures=int(values["consecutive_failures"]),
        row_count=int(values["row_count"]),
        data_path=str(values["data_path"]),
        source_note=str(values["source_note"]),
        license_note=str(values["license_note"]),
        redistribution_allowed=bool(values["redistribution_allowed"]),
        error_message=values["error_message"],
        created_at=str(values["created_at"]),
        updated_at=str(values["updated_at"]),
        owner_id=str(values["owner_id"]),
        visibility=str(values["visibility"]),
        enabled=bool(values["enabled"]),
        maintenance_enabled=bool(values["maintenance_enabled"]),
        is_owner=bool(owner_id and str(values["owner_id"]) == owner_id),
    )


def _series_id(provider: str, provider_symbol: str) -> str:
    digest = hashlib.sha256(f"{provider}:{provider_symbol}".encode()).hexdigest()[:12]
    safe = re.sub(r"[^a-z0-9]+", "_", provider_symbol.lower()).strip("_")
    return f"market_{safe}_{digest}"


def _price_columns() -> list[str]:
    return ["date", "open", "high", "low", "close", "adj_close", "volume"]


def _list_get(values: Any, index: int, default: Any = None) -> Any:
    if not isinstance(values, list) or index >= len(values):
        return default
    value = values[index]
    return default if value is None else value


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()
