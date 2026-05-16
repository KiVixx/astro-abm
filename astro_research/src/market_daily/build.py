from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from market_daily.config import AssetConfig, MarketDailyConfig
from market_daily.features import build_market_daily_features
from market_daily.providers.fred import FREDProvider
from market_daily.providers.local_csv import LocalCSVProvider
from market_daily.providers.yfinance_optional import YFinanceProvider


def build_market_daily_dataset(
    config: MarketDailyConfig,
    *,
    root: str | Path,
    assets: tuple[str, ...] | None = None,
    source: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = [
        asset_config
        for asset_name, asset_config in config.assets.items()
        if (not assets or asset_name in assets) and (not source or asset_config.source == source)
    ]
    providers = _providers(config=config, root=root)
    bars = []
    errors = []
    for asset_config in selected:
        provider = providers.get(asset_config.source)
        if provider is None:
            errors.append(f"{asset_config.asset}: provider not configured: {asset_config.source}")
            continue
        fetch_start = max(start or asset_config.start_date, asset_config.start_date)
        fetch_end = end or date.today()
        try:
            frame = provider.fetch_daily_bars(asset=asset_config, start=fetch_start, end=fetch_end)
        except Exception as exc:
            errors.append(f"{asset_config.asset}: {exc}")
            continue
        if frame.empty:
            continue
        frame = frame.copy()
        frame["data_version"] = config.data_version
        bars.append(frame)
    bar_frame = pd.concat(bars, ignore_index=True) if bars else pd.DataFrame()
    feature_frame = build_market_daily_features(bar_frame, data_version=config.data_version)
    if errors:
        bar_frame.attrs["warnings"] = errors
        feature_frame.attrs["warnings"] = errors
    return bar_frame, feature_frame


def export_market_dataset(bars: pd.DataFrame, features: pd.DataFrame, output_dir: str | Path, *, write_parquet: bool = True) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    tables = {
        "market_daily_bars": bars,
        "market_daily_features": features,
    }
    for name, frame in tables.items():
        csv_path = output / f"{name}.csv"
        frame.to_csv(csv_path, index=False)
        paths[f"{name}.csv"] = csv_path
        if write_parquet:
            parquet_path = output / f"{name}.parquet"
            frame.to_parquet(parquet_path, index=False)
            paths[f"{name}.parquet"] = parquet_path
    return paths


def _providers(*, config: MarketDailyConfig, root: str | Path) -> dict[str, object]:
    return {
        "local_csv": LocalCSVProvider(root=root),
        "fred": FREDProvider(provider_config=config.providers.get("fred", {})),
        "yfinance": YFinanceProvider(),
    }
