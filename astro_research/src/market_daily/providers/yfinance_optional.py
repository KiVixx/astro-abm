from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from market_daily.config import AssetConfig
from market_daily.normalize import normalize_market_bars
from market_daily.providers.base import MarketDailyProvider


class YFinanceProvider(MarketDailyProvider):
    source = "yfinance"

    def __init__(self):
        try:
            import yfinance as yf
        except ImportError:
            self._yf = None
        else:
            self._yf = yf

    @property
    def available(self) -> bool:
        return self._yf is not None

    def fetch_daily_bars(self, *, asset: AssetConfig, start: date, end: date) -> pd.DataFrame:
        if not self.available:
            raise RuntimeError("yfinance is not installed; install it or switch this asset to local_csv/FRED.")
        raw = self._yf.download(
            asset.symbol,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
        if raw.empty:
            return raw
        raw = raw.reset_index()
        raw.columns = [str(column).lower().replace(" ", "_") for column in raw.columns]
        raw = raw.rename(columns={"date": "ts", "adj_close": "adj_close"})
        return normalize_market_bars(
            raw,
            asset=asset.asset,
            source=self.source,
            currency=asset.currency,
            market_timezone=asset.timezone,
            data_version="",
            source_note=f"yfinance:{asset.symbol}",
        )
