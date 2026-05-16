from __future__ import annotations

import math

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ts",
    "asset",
    "source",
    "ret_1d",
    "log_ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "realized_vol_5d",
    "realized_vol_20d",
    "realized_vol_60d",
    "drawdown_5d",
    "drawdown_20d",
    "drawdown_60d",
    "abs_ret_rank_252d",
    "is_extreme_absret_95",
    "is_extreme_absret_99",
    "data_version",
]


def build_market_daily_features(bars: pd.DataFrame, *, data_version: str) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)
    frames = []
    for (_, _), group in bars.sort_values(["asset", "source", "ts"]).groupby(["asset", "source"], sort=False):
        working = group.copy()
        price = pd.to_numeric(working["adj_close"].fillna(working["close"]), errors="coerce")
        working["ret_1d"] = price.pct_change(1)
        working["log_ret_1d"] = np.log(price / price.shift(1))
        for horizon in (3, 5, 10, 20):
            working[f"ret_{horizon}d"] = price.pct_change(horizon)
        for horizon in (5, 20, 60):
            working[f"realized_vol_{horizon}d"] = np.sqrt((working["log_ret_1d"] ** 2).rolling(horizon, min_periods=2).sum())
            working[f"drawdown_{horizon}d"] = _rolling_max_drawdown(price, horizon)
        abs_ret = working["log_ret_1d"].abs()
        working["abs_ret_rank_252d"] = abs_ret.rolling(252, min_periods=20).apply(_last_percentile_rank, raw=True)
        working["is_extreme_absret_95"] = working["abs_ret_rank_252d"] >= 0.95
        working["is_extreme_absret_99"] = working["abs_ret_rank_252d"] >= 0.99
        working["data_version"] = data_version
        frames.append(working[FEATURE_COLUMNS])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FEATURE_COLUMNS)


def _rolling_max_drawdown(price: pd.Series, window: int) -> pd.Series:
    return price.rolling(window, min_periods=2).apply(_max_drawdown, raw=True)


def _max_drawdown(values: np.ndarray) -> float:
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return math.nan
    running_max = np.maximum.accumulate(values)
    drawdowns = values / running_max - 1.0
    return float(np.min(drawdowns))


def _last_percentile_rank(values: np.ndarray) -> float:
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return math.nan
    return float(np.mean(values <= values[-1]))
