from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Sequence

from astro_abm.config import load_market_data_settings
from astro_abm.etl.pipeline import normalize_to_utc_hour
from astro_abm.features.ephemeris import EphemerisCalculator, build_ephemeris_feature_rows
from astro_abm.features.social_sentiment import LunarCrushClient, build_social_sentiment_feature_rows
from astro_abm.features.space_weather import SpaceWeatherClient, build_space_weather_feature_rows
from astro_abm.market_data.binance_client import BinanceMarketDataClient
from astro_abm.market_data.tradfi import AlphaVantageProvider, PolygonProvider
from astro_abm.models import MarketBar
from astro_abm.storage.questdb import QuestDBHourlyFactWriter, QuestDBMarketBarWriter


@dataclass(frozen=True)
class LiveETLResult:
    run_ts: datetime
    market_bars_written: int = 0
    fact_rows_written: int = 0
    skipped: tuple[str, ...] = field(default_factory=tuple)


def run_live_etl(
    *,
    run_ts: datetime | None = None,
    crypto_symbols: Sequence[str] = ("BTCUSDT",),
    tradfi_symbols: Sequence[str] = ("SPY",),
    social_symbols: Sequence[str] = ("BTC",),
    binance_client: Any | None = None,
    tradfi_provider: Any | None = None,
    space_weather_client: Any | None = None,
    ephemeris_calculator: Any | None = None,
    lunarcrush_client: Any | None = None,
    market_bar_writer: Any | None = None,
    fact_writer: Any | None = None,
) -> LiveETLResult:
    bucket_ts = normalize_to_utc_hour(run_ts or datetime.now(UTC))
    market_bar_writer = market_bar_writer or QuestDBMarketBarWriter()
    fact_writer = fact_writer or QuestDBHourlyFactWriter()
    skipped: list[str] = []

    market_bars: list[MarketBar] = []
    if crypto_symbols:
        binance_client = binance_client or BinanceMarketDataClient()
        for symbol in crypto_symbols:
            market_bars.extend(binance_client.fetch_recent_hourly_bars(symbol=symbol, limit=2))

    if tradfi_symbols:
        if tradfi_provider is None:
            skipped.append("tradfi:no_provider")
        else:
            try:
                start = (bucket_ts - timedelta(days=7)).date().isoformat()
                end = bucket_ts.date().isoformat()
                for symbol in tradfi_symbols:
                    market_bars.extend(_fetch_tradfi_bars(tradfi_provider, symbol, start, end))
            except Exception as exc:
                skipped.append(f"tradfi:error:{type(exc).__name__}")

    market_bar_writer.write(market_bars)

    fact_rows: list[dict[str, Any]] = []
    fact_rows.extend(_collect_ephemeris_rows(bucket_ts, ephemeris_calculator))

    space_weather_client = space_weather_client or SpaceWeatherClient()
    space_rows = _collect_space_weather_rows(bucket_ts, space_weather_client)
    if space_rows:
        fact_rows.extend(space_rows)
    else:
        skipped.append("space_weather:no_complete_snapshot")

    if social_symbols:
        if lunarcrush_client is None:
            skipped.append("social:no_provider")
        else:
            try:
                fact_rows.extend(_collect_social_rows(social_symbols, lunarcrush_client, bucket_ts))
            except Exception as exc:
                skipped.append(f"social:error:{type(exc).__name__}")

    fact_writer.write(fact_rows)
    return LiveETLResult(
        run_ts=bucket_ts,
        market_bars_written=len(market_bars),
        fact_rows_written=len(fact_rows),
        skipped=tuple(skipped),
    )


def build_default_tradfi_provider() -> Any | None:
    settings = load_market_data_settings()
    provider = settings.default_tradfi_provider.lower()
    if provider == "polygon" and settings.polygon_api_key:
        return PolygonProvider(api_key=settings.polygon_api_key)
    if provider == "alpha_vantage" and settings.alpha_vantage_api_key:
        return AlphaVantageProvider(api_key=settings.alpha_vantage_api_key)
    return None


def build_default_lunarcrush_client() -> LunarCrushClient | None:
    api_key = load_market_data_settings().lunarcrush_api_key
    if not api_key:
        return None
    return LunarCrushClient(api_key=api_key)


def _fetch_tradfi_bars(provider: Any, symbol: str, start: str, end: str) -> list[MarketBar]:
    try:
        return provider.fetch_hourly_bars(symbol=symbol, start=start, end=end)
    except TypeError:
        return provider.fetch_hourly_bars(symbol=symbol)


def _collect_ephemeris_rows(bucket_ts: datetime, calculator: Any | None) -> list[dict[str, Any]]:
    calculator = calculator or EphemerisCalculator()
    return build_ephemeris_feature_rows(ts=bucket_ts, features=calculator.compute_features(bucket_ts))


def _collect_space_weather_rows(bucket_ts: datetime, client: Any) -> list[dict[str, Any]]:
    plasma = _latest_before(client.fetch_plasma(), "time_tag", bucket_ts)
    mag = _latest_before(client.fetch_magnetometer(), "time_tag", bucket_ts)
    xray = _latest_before(client.fetch_xray_flux(), "time_tag", bucket_ts)
    kp = _latest_before(client.fetch_hourly_kp(), "ts", bucket_ts)
    if not all([plasma, mag, xray, kp]):
        return []

    observed_ts = max(plasma["time_tag"], mag["time_tag"], xray["time_tag"], kp["ts"])
    return build_space_weather_feature_rows(
        ts=bucket_ts,
        solar_wind_speed=float(plasma["speed"]),
        imf_bz=float(mag["bz_gsm"]),
        xray_flux=float(xray["flux"]),
        kp_index=float(kp["kp_index"]),
        observed_ts=observed_ts,
        available_ts=datetime.now(UTC),
    )


def _collect_social_rows(symbols: Iterable[str], client: Any, bucket_ts: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    available_ts = datetime.now(UTC)
    for symbol in symbols:
        points = client.fetch_normalized_rows(symbol=symbol, hours_back=24)
        for point in points:
            if point["ts"] != bucket_ts:
                continue
            rows.extend(
                build_social_sentiment_feature_rows(
                    symbol=point["symbol"],
                    ts=point["ts"],
                    social_volume=point.get("social_volume"),
                    sentiment_score=point.get("sentiment_score"),
                    social_contributors=point.get("social_contributors"),
                    average_sentiment=point.get("average_sentiment"),
                    social_dominance=point.get("social_dominance"),
                    observed_ts=point["ts"],
                    available_ts=available_ts,
                )
            )
    return rows


def _latest_before(rows: Iterable[dict[str, Any]], timestamp_key: str, bucket_ts: datetime) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get(timestamp_key) is not None and row[timestamp_key] <= bucket_ts]
    if not candidates:
        return None
    return max(candidates, key=lambda row: row[timestamp_key])


def _split_env_list(name: str, default: str) -> tuple[str, ...]:
    value = os.getenv(name, default)
    return tuple(item.strip().upper() for item in value.split(",") if item.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one Astro ABM live ETL collection.")
    parser.add_argument("--run-ts", help="UTC timestamp to align to, defaults to now.")
    args = parser.parse_args(argv)
    run_ts = datetime.fromisoformat(args.run_ts.replace("Z", "+00:00")) if args.run_ts else None

    result = run_live_etl(
        run_ts=run_ts,
        crypto_symbols=_split_env_list("ASTRO_ABM_CRYPTO_SYMBOLS", "BTCUSDT"),
        tradfi_symbols=_split_env_list("ASTRO_ABM_TRADFI_SYMBOLS", "SPY"),
        social_symbols=_split_env_list("ASTRO_ABM_SOCIAL_SYMBOLS", "BTC"),
        tradfi_provider=build_default_tradfi_provider(),
        lunarcrush_client=build_default_lunarcrush_client(),
    )
    print(
        "Astro ABM ETL complete: "
        f"run_ts={result.run_ts.isoformat()} "
        f"market_bars={result.market_bars_written} "
        f"facts={result.fact_rows_written} "
        f"skipped={','.join(result.skipped) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
