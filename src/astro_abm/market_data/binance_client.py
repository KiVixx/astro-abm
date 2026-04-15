from __future__ import annotations

from datetime import UTC, datetime

from astro_abm.models import MarketBar


class BinanceMarketDataClient:
    def __init__(self, client=None):
        self._client = client or self._build_default_client()

    @staticmethod
    def _build_default_client():
        from binance.client import Client

        return Client()

    def fetch_recent_hourly_bars(self, symbol: str, limit: int = 500) -> list[MarketBar]:
        interval = self._client.KLINE_INTERVAL_1HOUR
        rows = self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        return [self._normalize_row(symbol, row) for row in rows]

    @staticmethod
    def _normalize_row(symbol: str, row: list) -> MarketBar:
        ts = datetime.fromtimestamp(row[0] / 1000, tz=UTC)
        observed_ts = datetime.fromtimestamp(row[6] / 1000, tz=UTC)
        return MarketBar(
            symbol=symbol,
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
