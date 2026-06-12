from __future__ import annotations

import re

from astro_abm_api.models.asset import MarketSeriesProfile


SUPPORTED_MARKET_SERIES: tuple[MarketSeriesProfile, ...] = (
    MarketSeriesProfile(
        asset="BTC",
        label="Bitcoin",
        series_type="crypto_price",
        aliases=["BTC", "XBT"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local/FRED market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="ETH",
        label="Ethereum",
        series_type="crypto_price",
        aliases=["ETH"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local/FRED market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="SPX",
        label="S&P 500",
        series_type="equity_index",
        aliases=["SPX", "S&P500", "S&P 500"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="NDX",
        label="Nasdaq 100",
        series_type="equity_index",
        aliases=["NDX", "NASDAQ100", "NASDAQ 100"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local/FRED market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="GOLD",
        label="Gold",
        series_type="commodity_price",
        aliases=["GOLD", "Gold", "XAU", "XAUUSD"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="DXY",
        label="US Dollar Index",
        series_type="currency_index",
        aliases=["DXY", "USD_INDEX"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="VIX",
        label="CBOE Volatility Index",
        series_type="volatility_index",
        aliases=["VIX"],
        market_daily_supported=True,
        notes=["Daily market series is supported when local/FRED market_daily data is available."],
    ),
    MarketSeriesProfile(
        asset="US10Y",
        label="US 10-Year Treasury Yield",
        series_type="rate_series",
        aliases=["US10Y", "10Y", "DGS10"],
        market_daily_supported=True,
        notes=["Daily rate series is supported when local/FRED market_daily data is available."],
    ),
)


def alias_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.strip().upper())


ALIAS_TO_ASSET: dict[str, str] = {
    alias_key(alias): profile.asset
    for profile in SUPPORTED_MARKET_SERIES
    for alias in (profile.asset, *profile.aliases)
}
PROFILE_BY_ASSET: dict[str, MarketSeriesProfile] = {
    profile.asset: profile for profile in SUPPORTED_MARKET_SERIES
}


def list_supported_market_series() -> list[MarketSeriesProfile]:
    return list(SUPPORTED_MARKET_SERIES)


def normalize_asset_id(asset: str) -> str:
    stripped = asset.strip()
    canonical = ALIAS_TO_ASSET.get(alias_key(stripped))
    return canonical or stripped


def normalize_asset_ids(assets: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for asset in assets:
        value = normalize_asset_id(asset)
        if not value:
            continue
        seen_key = alias_key(value)
        if seen_key in seen:
            continue
        seen.add(seen_key)
        normalized.append(value)
    return normalized


def profile_for_asset(asset: str) -> MarketSeriesProfile:
    canonical = ALIAS_TO_ASSET.get(alias_key(asset))
    if canonical:
        return PROFILE_BY_ASSET[canonical]
    clean_asset = asset.strip()
    return MarketSeriesProfile(
        asset=clean_asset,
        label=clean_asset,
        series_type="custom",
        aliases=[clean_asset] if clean_asset else [],
        market_daily_supported=False,
        supported=False,
        notes=["Custom asset accepted for backward compatibility, but no local daily market series is registered."],
    )


def profiles_for_assets(assets: list[str]) -> list[MarketSeriesProfile]:
    return [profile_for_asset(asset) for asset in assets]
