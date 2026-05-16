from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

from market_daily.config import AssetConfig
from market_daily.normalize import normalize_market_bars
from market_daily.providers.base import MarketDailyProvider


class FREDProvider(MarketDailyProvider):
    source = "fred"

    def __init__(self, *, provider_config: dict[str, Any] | None = None):
        load_dotenv(dotenv_path=Path.cwd() / ".env")
        provider_config = provider_config or {}
        api_key_env = str(provider_config.get("api_key_env", "FRED_API_KEY"))
        self.api_key = os.getenv(api_key_env)
        self.diagnostics: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def fetch_daily_bars(self, *, asset: AssetConfig, start: date, end: date) -> pd.DataFrame:
        if not self.available:
            raise RuntimeError("FRED API key is not configured; set FRED_API_KEY or use a local CSV source.")
        raw = self.fetch_observations(series_id=asset.symbol, start=start, end=end)
        if raw.empty:
            return raw
        raw = raw.rename(columns={"value": "close"})
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

    def fetch_observations(self, *, series_id: str, start: date, end: date) -> pd.DataFrame:
        if not self.available:
            raise RuntimeError("FRED API key is not configured; set FRED_API_KEY or use a local CSV source.")
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }
        diagnostic = {
            "series_id": series_id,
            "source": self.source,
            "request_params": _safe_params(params),
            "response_status": None,
            "row_count": 0,
            "error_message": "",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }
        try:
            response = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params=params,
                timeout=30,
            )
            diagnostic["response_status"] = response.status_code
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            diagnostic["error_message"] = str(exc)
            self.diagnostics.append(diagnostic)
            raise
        rows = []
        for observation in payload.get("observations", []):
            value = observation.get("value")
            if value in (None, "."):
                continue
            rows.append({"ts": observation["date"], "series_id": series_id, "source": self.source, "value": float(value)})
        raw = pd.DataFrame(rows)
        diagnostic["row_count"] = int(len(raw))
        if raw.empty:
            diagnostic["error_message"] = "zero_rows"
        self.diagnostics.append(diagnostic)
        if raw.empty:
            return raw
        raw["ts"] = pd.to_datetime(raw["ts"], utc=True).dt.normalize()
        return raw

    def diagnostics_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.diagnostics)


def _safe_params(params: dict[str, Any]) -> str:
    safe = {key: value for key, value in params.items() if key != "api_key"}
    return "&".join(f"{key}={value}" for key, value in safe.items())
