from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd

from market_daily.config import AssetConfig


@dataclass(frozen=True)
class MarketDailyCoverage:
    asset: str
    source: str
    start: date | None
    end: date | None


class MarketDailyProvider(ABC):
    source: str

    @abstractmethod
    def fetch_daily_bars(self, *, asset: AssetConfig, start: date, end: date) -> pd.DataFrame:
        raise NotImplementedError
