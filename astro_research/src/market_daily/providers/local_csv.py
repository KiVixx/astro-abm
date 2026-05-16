from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from market_daily.config import AssetConfig
from market_daily.normalize import normalize_market_bars
from market_daily.providers.base import MarketDailyProvider


class LocalCSVProvider(MarketDailyProvider):
    source = "local_csv"

    def __init__(self, *, root: str | Path | None = None):
        self.root = Path(root) if root else Path.cwd()

    def fetch_daily_bars(self, *, asset: AssetConfig, start: date, end: date) -> pd.DataFrame:
        if not asset.path:
            raise ValueError(f"Local CSV asset requires a path: {asset.asset}")
        path = Path(asset.path)
        if not path.is_absolute():
            path = self.root / path
        if not path.exists():
            raise FileNotFoundError(f"Local CSV not found for {asset.asset}: {path}")
        raw = pd.read_csv(path)
        frame = normalize_market_bars(
            raw,
            asset=asset.asset,
            source=self.source,
            currency=asset.currency,
            market_timezone=asset.timezone,
            data_version="",
            source_note=f"local_csv:{path}",
        )
        mask = (frame["ts"].dt.date >= start) & (frame["ts"].dt.date <= end)
        return frame.loc[mask].reset_index(drop=True)
