from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd
import requests

from market_daily.config import AssetConfig
from market_daily.normalize import normalize_market_bars
from market_daily.providers.base import MarketDailyProvider


class FREDProvider(MarketDailyProvider):
    source = "fred"

    def __init__(self, *, provider_config: dict[str, Any] | None = None):
        provider_config = provider_config or {}
        api_key_env = str(provider_config.get("api_key_env", "FRED_API_KEY"))
        self.api_key = os.getenv(api_key_env)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def fetch_daily_bars(self, *, asset: AssetConfig, start: date, end: date) -> pd.DataFrame:
        if not self.available:
            raise RuntimeError("FRED API key is not configured; set FRED_API_KEY or use a local CSV source.")
        response = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": asset.symbol,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
            },
            timeout=30,
        )
        response.raise_for_status()
        rows = []
        for observation in response.json().get("observations", []):
            value = observation.get("value")
            if value in (None, "."):
                continue
            rows.append({"date": observation["date"], "close": float(value)})
        raw = pd.DataFrame(rows)
        if raw.empty:
            return raw
        raw["open"] = raw["close"]
        raw["high"] = raw["close"]
        raw["low"] = raw["close"]
        raw["adj_close"] = raw["close"]
        raw["volume"] = pd.NA
        return normalize_market_bars(
            raw,
            asset=asset.asset,
            source=self.source,
            currency=asset.currency,
            market_timezone=asset.timezone,
            data_version="",
            source_note=f"fred:{asset.symbol}",
        )
