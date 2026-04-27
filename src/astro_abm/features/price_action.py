from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd


PRICE_ACTION_METRICS = [
    "price_return_1h",
    "price_log_return_1h",
    "price_range_pct",
    "price_drawdown_24h",
    "price_realized_vol_24h",
    "price_downside_vol_24h",
    "price_volume_zscore_24h",
    "price_shock_score",
]


def compute_price_action_features(frame: pd.DataFrame, rolling_hours: int = 24) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    df = frame.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values(["symbol", "ts"])
    groups = df.groupby("symbol", group_keys=False)

    df["price_return_1h"] = groups["close"].pct_change()
    df["price_log_return_1h"] = pd.to_numeric(
        groups["close"].transform(lambda series: (series / series.shift(1)).map(_safe_log)),
        errors="coerce",
    )
    df["price_range_pct"] = (df["high"] - df["low"]) / df["close"]
    df["price_drawdown_24h"] = groups["close"].transform(lambda series: series / series.rolling(rolling_hours, min_periods=2).max() - 1.0)
    df["price_realized_vol_24h"] = groups["price_log_return_1h"].transform(
        lambda series: series.rolling(rolling_hours, min_periods=2).std()
    )
    df["price_downside_vol_24h"] = groups["price_log_return_1h"].transform(
        lambda series: series.where(series < 0).rolling(rolling_hours, min_periods=2).std()
    )
    df["price_volume_zscore_24h"] = groups["volume"].transform(_rolling_zscore)
    df["price_shock_score"] = (df["price_log_return_1h"].abs() / df["price_realized_vol_24h"]).replace([float("inf"), -float("inf")], pd.NA)
    return df


def build_price_action_feature_rows(frame: pd.DataFrame, *, source: str = "price_action") -> list[dict[str, Any]]:
    features = compute_price_action_features(frame)
    rows: list[dict[str, Any]] = []
    for record in features.to_dict(orient="records"):
        ts = pd.Timestamp(record["ts"]).to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        for metric_name in PRICE_ACTION_METRICS:
            metric_value = _nullable_float(record.get(metric_name))
            if metric_value is None:
                continue
            rows.append(
                {
                    "ts": ts,
                    "entity_type": "price_action",
                    "entity_id": record["symbol"],
                    "source": source,
                    "interval": "1h",
                    "asset_class": "crypto",
                    "market": record.get("market_type", "spot"),
                    "region": "GLOBAL",
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "observed_ts": ts,
                    "available_ts": ts,
                    "quality_flag": "derived",
                }
            )
    return rows


def _safe_log(value) -> float | None:
    number = float(value) if value is not None else float("nan")
    if not math.isfinite(number) or number <= 0:
        return float("nan")
    return math.log(number)


def _rolling_zscore(series: pd.Series) -> pd.Series:
    rolling = series.rolling(24, min_periods=2)
    mean = rolling.mean()
    std = rolling.std().replace(0, pd.NA)
    return (series - mean) / std


def _nullable_float(value) -> float | None:
    if value is None or value is pd.NA:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number
