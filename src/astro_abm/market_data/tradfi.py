from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests

from astro_abm.models import MarketBar


def _infer_market_type(symbol: str) -> str:
    return "etf" if symbol.upper() == "SPY" else "equity"


class PolygonProvider:
    base_url = "https://api.polygon.io"

    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def build_url(self, symbol: str, start: str, end: str) -> str:
        return (
            f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/hour/{start}/{end}"
            f"?adjusted=true&sort=asc&limit=50000&apiKey={self.api_key}"
        )

    def fetch_hourly_bars(self, symbol: str, start: str, end: str) -> list[MarketBar]:
        response = self.session.get(self.build_url(symbol, start, end), timeout=30)
        response.raise_for_status()
        return self.parse_aggregate_response(response.json())

    def parse_aggregate_response(self, payload: dict) -> list[MarketBar]:
        symbol = payload.get("ticker", "")
        bars: list[MarketBar] = []
        for item in payload.get("results", []):
            ts = datetime.fromtimestamp(item["t"] / 1000, tz=UTC)
            bars.append(
                MarketBar(
                    symbol=symbol,
                    ts=ts,
                    open=float(item["o"]),
                    high=float(item["h"]),
                    low=float(item["l"]),
                    close=float(item["c"]),
                    volume=float(item["v"]),
                    source="polygon",
                    venue="polygon",
                    market_type=_infer_market_type(symbol),
                    asset_class="tradfi",
                    quote_volume=None,
                    trade_count=int(item["n"]) if item.get("n") is not None else None,
                    vwap=float(item["vw"]) if item.get("vw") is not None else None,
                    observed_ts=ts,
                    available_ts=ts,
                    complete=True,
                )
            )
        return bars


class AlphaVantageProvider:
    base_url = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def fetch_hourly_bars(self, symbol: str) -> list[MarketBar]:
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "60min",
            "adjusted": "true",
            "extended_hours": "false",
            "outputsize": "full",
            "apikey": self.api_key,
        }
        response = self.session.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        return self.parse_intraday_response(response.json())

    def parse_intraday_response(self, payload: dict) -> list[MarketBar]:
        metadata = payload.get("Meta Data", {})
        symbol = metadata.get("2. Symbol", "")
        tz_name = metadata.get("6. Time Zone", "US/Eastern")
        tzinfo = ZoneInfo(tz_name)
        series = payload.get("Time Series (60min)", {})
        bars: list[MarketBar] = []
        for timestamp, item in sorted(series.items()):
            local_ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tzinfo)
            ts = local_ts.astimezone(UTC)
            bars.append(
                MarketBar(
                    symbol=symbol,
                    ts=ts,
                    open=float(item["1. open"]),
                    high=float(item["2. high"]),
                    low=float(item["3. low"]),
                    close=float(item["4. close"]),
                    volume=float(item["5. volume"]),
                    source="alpha_vantage",
                    venue="alpha_vantage",
                    market_type=_infer_market_type(symbol),
                    asset_class="tradfi",
                    observed_ts=ts,
                    available_ts=ts,
                    complete=True,
                )
            )
        return bars
