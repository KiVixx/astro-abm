from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

import requests


BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"


@dataclass(frozen=True)
class BinanceDerivativeBackfillResult:
    fetched: int
    written: int
    skipped_existing: int
    errors: tuple[str, ...]


class BinanceFuturesDataClient:
    def __init__(self, base_url: str = BINANCE_FUTURES_BASE_URL, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_funding_rates(
        self,
        *,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        limit: int = 1000,
        pause_seconds: float = 0.05,
    ) -> list[dict[str, Any]]:
        start_ms = _to_ms(start_ts)
        end_ms = _to_ms(end_ts)
        rows: list[dict[str, Any]] = []

        while start_ms <= end_ms:
            payload = self._get(
                "/fapi/v1/fundingRate",
                params={
                    "symbol": symbol.upper(),
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": limit,
                },
            )
            if not payload:
                break
            rows.extend(payload)
            next_start = int(payload[-1]["fundingTime"]) + 1
            if next_start <= start_ms:
                break
            start_ms = next_start
            if len(payload) < limit:
                break
            if pause_seconds:
                time.sleep(pause_seconds)
        return rows

    def fetch_open_interest_history(
        self,
        *,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        period: str = "1h",
        limit: int = 500,
        pause_seconds: float = 0.05,
    ) -> list[dict[str, Any]]:
        start_ms = _to_ms(start_ts)
        end_ms = _to_ms(end_ts)
        rows: list[dict[str, Any]] = []

        while start_ms <= end_ms:
            payload = self._get(
                "/futures/data/openInterestHist",
                params={
                    "symbol": symbol.upper(),
                    "period": period,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": limit,
                },
            )
            if not payload:
                break
            rows.extend(payload)
            next_start = int(payload[-1]["timestamp"]) + int(timedelta(hours=1).total_seconds() * 1000)
            if next_start <= start_ms:
                break
            start_ms = next_start
            if len(payload) < limit:
                break
            if pause_seconds:
                time.sleep(pause_seconds)
        return rows

    def fetch_current_open_interest(self, *, symbol: str) -> dict[str, Any]:
        return self._get(
            "/fapi/v1/openInterest",
            params={"symbol": symbol.upper()},
        )

    def _get(self, path: str, *, params: dict[str, Any]) -> Any:
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()


def build_funding_feature_rows(
    payload: Sequence[dict[str, Any]],
    *,
    end_ts: datetime,
    expand_hours: int = 8,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    end_utc = end_ts.astimezone(UTC)
    for item in payload:
        symbol = str(item["symbol"]).upper()
        observed_ts = datetime.fromtimestamp(int(item["fundingTime"]) / 1000, tz=UTC)
        rate = float(item["fundingRate"])
        mark_price = _nullable_float(item.get("markPrice"))
        for offset in range(expand_hours):
            ts = observed_ts + timedelta(hours=offset)
            if ts >= end_utc:
                continue
            rows.extend(
                _derivative_metric_rows(
                    ts=ts,
                    symbol=symbol,
                    metrics=[
                        ("funding_rate", rate),
                        ("funding_rate_annualized", rate * 3 * 365),
                        ("funding_mark_price", mark_price),
                    ],
                    observed_ts=observed_ts,
                    quality_flag="derived",
                )
            )
    return rows


def build_open_interest_feature_rows(payload: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        ts = datetime.fromtimestamp(int(item["timestamp"]) / 1000, tz=UTC)
        symbol = str(item["symbol"]).upper()
        rows.extend(
            _derivative_metric_rows(
                ts=ts,
                symbol=symbol,
                metrics=[
                    ("open_interest", _nullable_float(item.get("sumOpenInterest"))),
                    ("open_interest_value", _nullable_float(item.get("sumOpenInterestValue"))),
                ],
                observed_ts=ts,
                quality_flag="final",
            )
        )
    return rows


def build_current_open_interest_feature_rows(
    payload: Sequence[dict[str, Any]],
    *,
    bucket_ts: datetime,
    source: str = "binance_futures_current",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        symbol = str(item["symbol"]).upper()
        observed_ts = datetime.fromtimestamp(int(item["time"]) / 1000, tz=UTC)
        rows.extend(
            _derivative_metric_rows(
                ts=bucket_ts.astimezone(UTC),
                symbol=symbol,
                metrics=[("open_interest", _nullable_float(item.get("openInterest")))],
                observed_ts=observed_ts,
                quality_flag="official",
                source=source,
                notes="Binance current open interest snapshot; forward-collected hourly.",
            )
        )
    return rows


def _derivative_metric_rows(
    *,
    ts: datetime,
    symbol: str,
    metrics: Sequence[tuple[str, float | None]],
    observed_ts: datetime,
    quality_flag: str,
    source: str = "binance_futures",
    notes: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for metric_name, metric_value in metrics:
        if metric_value is None:
            continue
        rows.append(
            {
                "ts": ts,
                "entity_type": "derivatives",
                "entity_id": symbol,
                "source": source,
                "interval": "1h",
                "asset_class": "crypto",
                "market": "perp",
                "region": "GLOBAL",
                "metric_name": metric_name,
                "metric_value": metric_value,
                "observed_ts": observed_ts,
                "available_ts": observed_ts,
                "quality_flag": quality_flag,
                "notes": notes,
            }
        )
    return rows


def _to_ms(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp() * 1000)


def _nullable_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
