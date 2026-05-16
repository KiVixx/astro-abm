from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from research.bootstrap import bootstrap_ci, permutation_p_value
from research.config import EventStudyConfig
from research.event_windows import select_event_windows
from research.io import read_aspect_chunk_windows, read_optional_table, read_table
from research.multiple_testing import benjamini_hochberg


METRICS = (
    "mean_return",
    "median_return",
    "cumulative_log_return",
    "realized_volatility",
    "max_drawdown",
    "extreme_move_frequency",
    "positive_hit_rate",
    "negative_hit_rate",
)


@dataclass(frozen=True)
class EventStudyOutput:
    results: pd.DataFrame
    metadata: dict


def run_event_study(config: EventStudyConfig, *, root: str | Path | None = None) -> EventStudyOutput:
    root_path = Path(root or Path.cwd())
    market = _prepare_market(read_table(_resolve(root_path, config.market_features_path)))
    event_windows = read_optional_table(_resolve(root_path, config.astro_event_windows_path))
    aspect_chunk_windows = read_aspect_chunk_windows(_resolve(root_path, config.aspect_chunks_dir))
    if not aspect_chunk_windows.empty:
        event_windows = pd.concat([event_windows, aspect_chunk_windows], ignore_index=True) if not event_windows.empty else aspect_chunk_windows
    daily_features = read_optional_table(_resolve(root_path, config.astro_daily_features_path))
    if not event_windows.empty:
        event_windows["ts"] = pd.to_datetime(event_windows["ts"], utc=True).dt.normalize()
    if not daily_features.empty:
        daily_features["ts"] = pd.to_datetime(daily_features["ts"], utc=True).dt.normalize()

    rows = []
    placebo_cache: dict[tuple[str, str, str, str], float] = {}
    for event_type, group in config.event_groups.items():
        for requested_window in config.windows:
            selection = select_event_windows(
                event_type=event_type,
                group=group,
                window_name=requested_window,
                astro_event_windows=event_windows,
                astro_daily_features=daily_features,
            )
            if selection.events.empty:
                continue
            for asset in sorted(market["asset"].dropna().unique()):
                asset_market = market[market["asset"] == asset].copy()
                if asset_market.empty:
                    continue
                event_dates = set(selection.events["ts"])
                for baseline_type in config.baseline_types:
                    event_values = _event_metric_values(selection.events, asset_market)
                    baseline_values = _baseline_metric_values(
                        selection.events,
                        asset_market,
                        baseline_type=baseline_type,
                        exclude_event_windows=config.exclude_event_windows,
                    )
                    for metric in METRICS:
                        values = event_values.get(metric, [])
                        baseline_metric = baseline_values.get(metric, [])
                        effect = _mean(values)
                        baseline = _mean(baseline_metric)
                        ci_low, ci_high = bootstrap_ci(
                            values,
                            samples=config.bootstrap_samples,
                            seed=config.random_seed,
                        )
                        p_value = permutation_p_value(
                            values,
                            baseline_metric,
                            samples=config.bootstrap_samples,
                            seed=config.random_seed,
                        )
                        placebo_key = (event_type, requested_window, asset, metric)
                        if placebo_key not in placebo_cache:
                            placebo_cache[placebo_key] = _placebo_percentile(
                                real_effect=effect,
                                metric=metric,
                                events=selection.events,
                                market=asset_market,
                                excluded_dates=event_dates,
                                samples=config.placebo_samples,
                                seed=config.random_seed,
                            )
                        placebo_percentile = placebo_cache[placebo_key]
                        rows.append(
                            {
                                "ts": datetime.now(UTC),
                                "run_id": config.run_id,
                                "event_type": event_type,
                                "asset": asset,
                                "window_name": f"{requested_window}|baseline={baseline_type}",
                                "metric": metric,
                                "effect_value": effect,
                                "baseline_value": baseline,
                                "effect_minus_baseline": effect - baseline if not math.isnan(effect) and not math.isnan(baseline) else math.nan,
                                "bootstrap_ci_low": ci_low,
                                "bootstrap_ci_high": ci_high,
                                "p_value": p_value,
                                "q_value_fdr": math.nan,
                                "n_events": int(selection.events["event_id"].nunique()),
                                "n_observations": int(len(selection.events)),
                                "data_version": config.data_version,
                                "calc_version": config.calc_version,
                                "source_note": f"calendar_day;placebo_percentile={placebo_percentile:.6f}",
                                "real_percentile_vs_placebo": placebo_percentile,
                            }
                        )
    results = pd.DataFrame(rows)
    if not results.empty:
        results["q_value_fdr"] = benjamini_hochberg(results["p_value"].tolist())
    return EventStudyOutput(
        results=results,
        metadata={
            "run_id": config.run_id,
            "assets": sorted(market["asset"].dropna().unique().tolist()),
            "event_groups": list(config.event_groups.keys()),
            "windows": list(config.windows),
        },
    )


def _prepare_market(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    working["weekday"] = working["ts"].dt.weekday
    working["month"] = working["ts"].dt.month
    for column in ("log_ret_1d", "is_extreme_absret_95"):
        if column not in working.columns:
            raise ValueError(f"market_daily_features missing required column: {column}")
    return working


def _event_metric_values(events: pd.DataFrame, market: pd.DataFrame) -> dict[str, list[float]]:
    joined = events.merge(market, on="ts", how="inner")
    return _metrics_by_event(joined)


def _baseline_metric_values(events: pd.DataFrame, market: pd.DataFrame, *, baseline_type: str, exclude_event_windows: bool) -> dict[str, list[float]]:
    baseline = market.copy()
    if exclude_event_windows:
        baseline = baseline[~baseline["ts"].isin(set(events["ts"]))]
    exact_dates = pd.to_datetime(events["exact_date_ts"], utc=True)
    if baseline_type == "month_matched":
        baseline = baseline[baseline["month"].isin(set(exact_dates.dt.month))]
    elif baseline_type == "weekday_matched":
        baseline = baseline[baseline["weekday"].isin(set(exact_dates.dt.weekday))]
    baseline = baseline.copy()
    baseline["event_id"] = "baseline"
    return _metrics_by_event(baseline)


def _metrics_by_event(frame: pd.DataFrame) -> dict[str, list[float]]:
    metrics = {metric: [] for metric in METRICS}
    if frame.empty:
        return metrics
    for _, group in frame.groupby("event_id", sort=False):
        returns = pd.to_numeric(group["log_ret_1d"], errors="coerce").dropna()
        if returns.empty:
            continue
        metrics["mean_return"].append(float(returns.mean()))
        metrics["median_return"].append(float(returns.median()))
        metrics["cumulative_log_return"].append(float(returns.sum()))
        metrics["realized_volatility"].append(float(np.sqrt(np.sum(returns**2))))
        metrics["max_drawdown"].append(_max_drawdown_from_returns(returns.to_numpy()))
        extreme = group.loc[returns.index, "is_extreme_absret_95"].astype(bool)
        metrics["extreme_move_frequency"].append(float(extreme.mean()))
        metrics["positive_hit_rate"].append(float((returns > 0).mean()))
        metrics["negative_hit_rate"].append(float((returns < 0).mean()))
    return metrics


def _max_drawdown_from_returns(log_returns: np.ndarray) -> float:
    equity = np.exp(np.cumsum(log_returns))
    running_max = np.maximum.accumulate(equity)
    return float(np.min(equity / running_max - 1.0))


def _placebo_percentile(
    *,
    real_effect: float,
    metric: str,
    events: pd.DataFrame,
    market: pd.DataFrame,
    excluded_dates: set,
    samples: int,
    seed: int,
) -> float:
    if math.isnan(real_effect) or events.empty or market.empty:
        return math.nan
    rng = np.random.default_rng(seed)
    event_dates = pd.to_datetime(events["exact_date_ts"], utc=True).drop_duplicates()
    eligible = market[~market["ts"].isin(excluded_dates)].copy()
    if eligible.empty:
        return math.nan
    effects = []
    for _ in range(samples):
        sampled_dates = []
        for month, count in event_dates.dt.month.value_counts().items():
            month_pool = eligible[eligible["month"] == month]["ts"].drop_duplicates().to_numpy()
            if len(month_pool) == 0:
                month_pool = eligible["ts"].drop_duplicates().to_numpy()
            sampled_dates.extend(rng.choice(month_pool, size=int(count), replace=len(month_pool) < count))
        pseudo = _pseudo_windows(pd.to_datetime(sampled_dates, utc=True), events)
        values = _event_metric_values(pseudo, market).get(metric, [])
        effects.append(_mean(values))
    clean = np.asarray([value for value in effects if not math.isnan(value)], dtype=float)
    if len(clean) == 0:
        return math.nan
    return float(np.mean(clean <= real_effect))


def _pseudo_windows(sampled_dates: pd.DatetimeIndex, real_events: pd.DataFrame) -> pd.DataFrame:
    template = real_events[["rel_day"]].drop_duplicates().sort_values("rel_day")
    rows = []
    for index, exact_date in enumerate(sampled_dates):
        for rel_day in template["rel_day"]:
            rows.append(
                {
                    "ts": exact_date.normalize() + timedelta(days=int(rel_day)),
                    "event_id": f"placebo_{index}",
                    "exact_date_ts": exact_date.normalize(),
                    "rel_day": int(rel_day),
                }
            )
    return pd.DataFrame(rows)


def _mean(values) -> float:
    array = np.asarray(values, dtype=float)
    array = array[~np.isnan(array)]
    if len(array) == 0:
        return math.nan
    return float(np.mean(array))


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
