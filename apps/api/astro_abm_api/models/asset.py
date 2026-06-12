from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketSeriesProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    label: str
    series_type: str
    aliases: list[str] = Field(default_factory=list)
    market_daily_supported: bool
    supported: bool = True
    notes: list[str] = Field(default_factory=list)
