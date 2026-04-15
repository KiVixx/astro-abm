from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    venue: str
    market_type: str
    asset_class: str
    quote_volume: float | None = None
    trade_count: int | None = None
    vwap: float | None = None
    observed_ts: datetime | None = None
    available_ts: datetime | None = None
    complete: bool = True
