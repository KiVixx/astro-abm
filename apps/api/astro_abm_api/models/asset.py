from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketSeriesProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    label: str
    series_type: str
    aliases: list[str] = Field(default_factory=list)
    market_daily_supported: bool
    supported: bool = True
    notes: list[str] = Field(default_factory=list)


class CustomMarketSeriesCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9^][A-Za-z0-9.^=_-]*$")
    label: str = Field(min_length=1, max_length=80)
    asset_type: Literal["equity", "etf", "equity_index"] = "equity"
    provider: Literal["yahoo"] = "yahoo"
    provider_symbol: str | None = Field(
        default=None,
        max_length=20,
        pattern=r"^[A-Za-z0-9^][A-Za-z0-9.^=_-]*$",
    )
    currency: str = Field(default="USD", min_length=3, max_length=8, pattern=r"^[A-Za-z]+$")
    market_timezone: str = Field(
        default="America/New_York",
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z_]+(?:/[A-Za-z0-9_+-]+)+$",
    )
    visibility: Literal["private", "public"] = "private"
    maintenance_enabled: bool = True

    @field_validator("symbol", "provider_symbol")
    @classmethod
    def normalize_symbols(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class CustomMarketSeriesUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    maintenance_enabled: bool | None = None
    visibility: Literal["private", "public"] | None = None


class CustomMarketSeriesRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    symbol: str
    label: str
    asset_type: str
    provider: str
    provider_symbol: str
    currency: str
    market_timezone: str
    frequency: str
    status: str
    coverage_start: str | None = None
    coverage_end: str | None = None
    latest_observation_date: str | None = None
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    consecutive_failures: int
    row_count: int
    source_note: str
    license_note: str
    redistribution_allowed: bool
    error_message: str | None = None
    created_at: str
    updated_at: str
    visibility: str
    enabled: bool
    maintenance_enabled: bool
    is_owner: bool


class MarketSeriesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    built_in: list[MarketSeriesProfile]
    custom: list[CustomMarketSeriesRecord]


class MarketSeriesRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: CustomMarketSeriesRecord
    status: str
    fetched_rows: int
    rows_written: int
    attempts: int
    adopted_existing: bool
    errors: list[str] = Field(default_factory=list)
