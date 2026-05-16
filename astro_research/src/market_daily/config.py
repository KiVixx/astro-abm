from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from astro_daily.calendar import parse_date
from astro_daily.config import _parse_simple_yaml


@dataclass(frozen=True)
class AssetConfig:
    asset: str
    source: str
    symbol: str
    timezone: str
    start_date: date
    currency: str
    path: str | None = None
    frequency: str = "daily"
    fallback_source: str | None = None
    fallback_path: str | None = None
    license_note: str = ""


@dataclass(frozen=True)
class MarketDailyConfig:
    data_version: str
    assets: dict[str, AssetConfig]
    providers: dict[str, dict[str, Any]]


def load_market_daily_config(path: str | Path) -> MarketDailyConfig:
    raw = _parse_simple_yaml(Path(path).read_text())
    data_version = str(raw.get("dataset", {}).get("data_version", "market_daily_v1"))
    assets = {
        asset: AssetConfig(
            asset=asset,
            source=str(values["source"]),
            symbol=str(values["symbol"]),
            timezone=str(values.get("timezone", "UTC")),
            start_date=parse_date(str(values["start_date"])),
            currency=str(values.get("currency", "USD")),
            path=str(values["path"]) if "path" in values else None,
            frequency=str(values.get("frequency", "daily")),
            fallback_source=str(values["fallback_source"]) if "fallback_source" in values else None,
            fallback_path=str(values["fallback_path"]) if "fallback_path" in values else None,
            license_note=str(values.get("license_note", "")),
        )
        for asset, values in raw.get("assets", {}).items()
    }
    return MarketDailyConfig(
        data_version=data_version,
        assets=assets,
        providers=raw.get("providers", {}),
    )
