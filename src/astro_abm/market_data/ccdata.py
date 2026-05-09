from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

import requests

from astro_abm.config import load_market_data_settings
from astro_abm.models import MarketBar


CCDATA_BASE_URL = "https://min-api.cryptocompare.com"


@dataclass(frozen=True)
class CCDataHourlyBar:
    bar: MarketBar
    conversion_type: str | None


class CCDataAggregateClient:
    def __init__(
        self,
        base_url: str = CCDATA_BASE_URL,
        session: requests.Session | None = None,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 30,
        max_attempts: int = 5,
        retry_sleep_seconds: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.api_key = api_key if api_key is not None else load_market_data_settings().ccdata_api_key
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.retry_sleep_seconds = max(0.0, retry_sleep_seconds)

    def fetch_hourly_bars(
        self,
        *,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        limit: int = 2000,
        pause_seconds: float = 1.0,
    ) -> list[MarketBar]:
        if end_ts <= start_ts:
            return []
        fsym, tsym = split_market_symbol(symbol)
        rows: dict[datetime, MarketBar] = {}
        cursor_end = end_ts

        while cursor_end > start_ts:
            span_hours = max(1, int((cursor_end - start_ts).total_seconds() // 3600))
            request_limit = min(limit, span_hours)
            payload = self._get_histohour(fsym=fsym, tsym=tsym, limit=request_limit, to_ts=cursor_end)
            bars = [bar for bar in self._normalize_payload(symbol=symbol, payload=payload)]
            for bar in bars:
                if start_ts <= bar.ts < end_ts:
                    rows[bar.ts] = bar
            if not bars:
                break
            earliest = min(bar.ts for bar in bars)
            if earliest <= start_ts or request_limit < limit:
                break
            cursor_end = earliest
            if pause_seconds:
                time.sleep(pause_seconds)

        return [rows[ts] for ts in sorted(rows)]

    def _get_histohour(self, *, fsym: str, tsym: str, limit: int, to_ts: datetime) -> dict:
        params = {
            "fsym": fsym,
            "tsym": tsym,
            "limit": limit,
            "toTs": int(to_ts.astimezone(UTC).timestamp()),
        }
        if self.api_key:
            params["api_key"] = self.api_key

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.session.get(
                    f"{self.base_url}/data/v2/histohour",
                    params=params,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("Response") in {None, "Success"}:
                    return payload
                message = payload.get("Message") or "CCData histohour request failed."
                raise ValueError(message)
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.retry_sleep_seconds * attempt)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _normalize_payload(*, symbol: str, payload: dict) -> Iterable[MarketBar]:
        for row in payload.get("Data", {}).get("Data", []):
            ts = datetime.fromtimestamp(int(row["time"]), tz=UTC)
            volume = float(row.get("volumefrom") or 0.0)
            quote_volume = float(row.get("volumeto") or 0.0)
            yield MarketBar(
                symbol=symbol.upper(),
                ts=ts,
                open=float(row.get("open") or 0.0),
                high=float(row.get("high") or 0.0),
                low=float(row.get("low") or 0.0),
                close=float(row.get("close") or 0.0),
                volume=volume,
                source="ccdata_aggregate",
                venue="ccdata",
                market_type="aggregate_proxy",
                asset_class="crypto",
                quote_volume=quote_volume,
                trade_count=None,
                observed_ts=ts + timedelta(hours=1),
                available_ts=ts + timedelta(hours=1),
                complete=True,
                quality_flag="proxy",
                is_proxy_data=True,
                is_imputed=False,
                raw_volume=volume,
                raw_quote_volume=quote_volume,
                conversion_type=row.get("conversionType") or None,
            )


def split_market_symbol(symbol: str) -> tuple[str, str]:
    normalized = symbol.strip().upper()
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if normalized.endswith(quote) and len(normalized) > len(quote):
            return normalized[: -len(quote)], quote
    raise ValueError(f"Cannot infer base/quote assets from symbol: {symbol}")
