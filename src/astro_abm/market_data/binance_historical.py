from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable, Sequence

import requests

from astro_abm.models import MarketBar


BINANCE_SPOT_BASE_URL = "https://api.binance.com"


@dataclass(frozen=True)
class BinanceSpotBackfillResult:
    symbol: str
    fetched: int
    written: int
    skipped_existing: int
    start_ts: datetime | None
    end_ts: datetime | None


class BinanceSpotHistoricalClient:
    def __init__(self, base_url: str = BINANCE_SPOT_BASE_URL, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_hourly_klines(
        self,
        *,
        symbol: str,
        start_ts: datetime,
        end_ts: datetime,
        limit: int = 1000,
        max_requests: int | None = None,
        pause_seconds: float = 0.05,
    ) -> list[MarketBar]:
        start_ms = _to_ms(start_ts)
        end_ms = _to_ms(end_ts)
        rows: list[MarketBar] = []
        requests_made = 0

        while start_ms < end_ms:
            if max_requests is not None and requests_made >= max_requests:
                break

            payload = self._get_klines(symbol=symbol, start_ms=start_ms, end_ms=end_ms, limit=limit)
            requests_made += 1
            if not payload:
                break

            bars = [self._normalize_kline(symbol, row) for row in payload]
            rows.extend(bars)
            next_start = int(payload[-1][0]) + int(timedelta(hours=1).total_seconds() * 1000)
            if next_start <= start_ms:
                break
            start_ms = next_start
            if len(payload) < limit:
                break
            if pause_seconds:
                time.sleep(pause_seconds)

        return rows

    def _get_klines(self, *, symbol: str, start_ms: int, end_ms: int, limit: int) -> list:
        response = self.session.get(
            f"{self.base_url}/api/v3/klines",
            params={
                "symbol": symbol.upper(),
                "interval": "1h",
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _normalize_kline(symbol: str, row: Sequence) -> MarketBar:
        ts = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
        observed_ts = datetime.fromtimestamp(int(row[6]) / 1000, tz=UTC)
        return MarketBar(
            symbol=symbol.upper(),
            ts=ts,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            source="binance",
            venue="binance",
            market_type="spot",
            asset_class="crypto",
            quote_volume=float(row[7]),
            trade_count=int(row[8]),
            observed_ts=observed_ts,
            available_ts=observed_ts,
            complete=True,
        )


def _to_ms(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp() * 1000)


def normalize_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
    return tuple(symbol.strip().upper() for symbol in symbols if symbol and symbol.strip())
