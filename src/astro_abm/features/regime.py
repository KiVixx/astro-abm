from __future__ import annotations

import math
from datetime import UTC
from typing import Any

import pandas as pd


REGIME_FEATURE_METRICS = [
    "regime_return_24h",
    "regime_realized_vol_24h",
    "regime_price_drawdown_24h",
    "regime_oi_change_24h",
    "regime_oi_zscore_168h",
    "regime_funding_rate",
    "regime_funding_zscore_168h",
    "regime_leverage_pressure",
    "regime_crowded_long_score",
    "regime_crowded_short_score",
    "regime_fragility_score",
]


REGIME_LABEL_METRICS = [
    "future_return_24h",
    "future_abs_return_24h",
    "future_realized_vol_24h",
    "future_drawdown_24h",
    "future_trend_persistence_24h",
    "future_liquidation_risk_proxy",
]


def compute_regime_features(frame: pd.DataFrame, *, short_window: int = 24, long_window: int = 168) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    df = _prepare_frame(frame)
    groups = df.groupby("symbol", group_keys=False)
    df["log_return_1h"] = groups["close"].transform(lambda series: (series / series.shift(1)).map(_safe_log))
    df["regime_return_24h"] = groups["close"].transform(lambda series: series / series.shift(short_window) - 1.0)
    df["regime_realized_vol_24h"] = groups["log_return_1h"].transform(lambda series: series.rolling(short_window, min_periods=2).std())
    df["regime_price_drawdown_24h"] = groups["close"].transform(lambda series: series / series.rolling(short_window, min_periods=2).max() - 1.0)
    df["regime_oi_change_24h"] = groups["open_interest"].transform(lambda series: series / series.shift(short_window) - 1.0)
    df["regime_oi_zscore_168h"] = groups["open_interest"].transform(lambda series: _rolling_zscore(series, long_window))
    df["regime_funding_rate"] = df["funding_rate"]
    df["regime_funding_zscore_168h"] = groups["funding_rate"].transform(lambda series: _rolling_zscore(series, long_window))

    positive_oi = df["regime_oi_zscore_168h"].clip(lower=0)
    positive_funding = df["regime_funding_zscore_168h"].clip(lower=0)
    negative_funding = (-df["regime_funding_zscore_168h"]).clip(lower=0)
    shock = (df["log_return_1h"].abs() / df["regime_realized_vol_24h"]).replace([float("inf"), -float("inf")], pd.NA)

    df["regime_leverage_pressure"] = positive_oi * df["regime_funding_zscore_168h"].abs()
    df["regime_crowded_long_score"] = positive_oi * positive_funding
    df["regime_crowded_short_score"] = positive_oi * negative_funding
    df["regime_fragility_score"] = positive_oi * shock
    return df


def compute_regime_labels(frame: pd.DataFrame, *, horizon_hours: int = 24) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if horizon_hours <= 0:
        raise ValueError("horizon_hours must be greater than 0.")
    if horizon_hours != 24:
        raise ValueError("Only horizon_hours=24 is supported by the current regime label metric names.")

    df = _prepare_frame(frame)
    groups = df.groupby("symbol", group_keys=False)
    df["log_return_1h"] = groups["close"].transform(lambda series: (series / series.shift(1)).map(_safe_log))
    df["future_return_24h"] = groups["close"].transform(lambda series: series.shift(-horizon_hours) / series - 1.0)
    df["future_abs_return_24h"] = df["future_return_24h"].abs()
    future_count = groups["log_return_1h"].transform(
        lambda series: _forward_rolling(series.shift(-1).notna().astype(float), horizon_hours, "sum", min_periods=1)
    )
    df["future_realized_vol_24h"] = groups["log_return_1h"].transform(
        lambda series: _forward_rolling(series.shift(-1), horizon_hours, "std", min_periods=2)
    )
    df["future_drawdown_24h"] = groups["close"].transform(
        lambda series: _forward_rolling(series.shift(-1), horizon_hours, "min", min_periods=1) / series - 1.0
    )
    future_sum = groups["log_return_1h"].transform(lambda series: _forward_rolling(series.shift(-1), horizon_hours, "sum", min_periods=1))
    future_abs_sum = groups["log_return_1h"].transform(
        lambda series: _forward_rolling(series.shift(-1).abs(), horizon_hours, "sum", min_periods=1)
    )
    df["future_trend_persistence_24h"] = (future_sum.abs() / future_abs_sum).replace([float("inf"), -float("inf")], pd.NA)
    current_vol = groups["log_return_1h"].transform(lambda series: series.rolling(horizon_hours, min_periods=2).std())
    df["future_liquidation_risk_proxy"] = (df["future_abs_return_24h"] / current_vol).replace([float("inf"), -float("inf")], pd.NA)
    incomplete = future_count < horizon_hours
    for metric_name in REGIME_LABEL_METRICS:
        df.loc[incomplete, metric_name] = pd.NA
    return df


def build_regime_feature_rows(frame: pd.DataFrame, *, source: str = "regime_features") -> list[dict[str, Any]]:
    return _build_rows(
        compute_regime_features(frame),
        metric_names=REGIME_FEATURE_METRICS,
        source=source,
        entity_type="regime",
        quality_flag="derived",
    )


def build_regime_label_rows(frame: pd.DataFrame, *, source: str = "regime_labels") -> list[dict[str, Any]]:
    return _build_rows(
        compute_regime_labels(frame),
        metric_names=REGIME_LABEL_METRICS,
        source=source,
        entity_type="regime_label",
        quality_flag="label",
    )


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values(["symbol", "ts"])
    for column in ("close", "open_interest", "funding_rate"):
        if column not in df.columns:
            df[column] = pd.NA
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _build_rows(
    frame: pd.DataFrame,
    *,
    metric_names: list[str],
    source: str,
    entity_type: str,
    quality_flag: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        ts = pd.Timestamp(record["ts"]).to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        for metric_name in metric_names:
            metric_value = _nullable_float(record.get(metric_name))
            if metric_value is None:
                continue
            rows.append(
                {
                    "ts": ts,
                    "entity_type": entity_type,
                    "entity_id": record["symbol"],
                    "source": source,
                    "interval": "1h",
                    "asset_class": "crypto",
                    "market": "perp",
                    "region": "GLOBAL",
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "observed_ts": ts,
                    "available_ts": ts,
                    "quality_flag": quality_flag,
                }
            )
    return rows


def _safe_log(value) -> float | None:
    number = float(value) if value is not None else float("nan")
    if not math.isfinite(number) or number <= 0:
        return float("nan")
    return math.log(number)


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    rolling = series.rolling(window, min_periods=max(2, min(window, 24)))
    mean = rolling.mean()
    std = rolling.std().replace(0, pd.NA)
    return (series - mean) / std


def _forward_rolling(series: pd.Series, window: int, operation: str, *, min_periods: int) -> pd.Series:
    rolling = series.iloc[::-1].rolling(window, min_periods=min_periods)
    if operation == "std":
        result = rolling.std()
    elif operation == "min":
        result = rolling.min()
    elif operation == "sum":
        result = rolling.sum()
    else:
        raise ValueError(f"Unsupported forward rolling operation: {operation}")
    return result.iloc[::-1]


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
