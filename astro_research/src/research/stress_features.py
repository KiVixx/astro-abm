from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.io import read_optional_table


STRESS_COLUMNS = [
    "ts",
    "stress_universe",
    "equity_stress_score",
    "vol_stress_score",
    "rates_stress_score",
    "credit_stress_score",
    "dollar_stress_score",
    "gold_stress_score",
    "crypto_stress_score",
    "cross_asset_stress_score",
    "component_count",
    "spx_drawdown_20d",
    "spx_drawdown_60d",
    "spx_realized_vol_20d",
    "spx_absret_percentile_252d",
    "vix_level",
    "vix_percentile_252d",
    "vix_change_5d",
    "us10y_change_5d",
    "us10y_change_20d",
    "yield_curve_10y2y",
    "hy_oas_level",
    "hy_oas_change_20d",
    "nfci_level",
    "btc_drawdown_20d",
    "btc_realized_vol_20d",
    "gold_return_20d",
    "is_equity_stress",
    "is_vol_stress",
    "is_rates_stress",
    "is_credit_stress",
    "is_gold_stress",
    "is_crypto_stress",
    "is_cross_asset_stress",
    "stress_regime",
    "data_version",
]


@dataclass(frozen=True)
class StressBuildResult:
    frame: pd.DataFrame
    warnings: tuple[str, ...]
    data_version: str
    component_coverage: pd.DataFrame


def build_financial_stress(config_path: str | Path, *, root: str | Path | None = None) -> StressBuildResult:
    root_path = Path(root or Path.cwd())
    raw = _parse_simple_yaml(Path(config_path).read_text())
    data_version = str(raw.get("dataset", {}).get("data_version", "financial_stress_v1"))
    universe = str(raw.get("dataset", {}).get("stress_universe", "global_cross_asset"))
    inputs = raw.get("inputs", {})
    thresholds = raw.get("thresholds", {})
    market = read_optional_table(_resolve(root_path, str(inputs.get("market_features_path", ""))))
    macro = read_optional_table(_resolve(root_path, str(inputs.get("macro_observations_path", ""))))
    warnings = []
    if market.empty and macro.empty:
        warnings.append("No market or macro inputs found; financial stress output is empty.")
        return StressBuildResult(pd.DataFrame(columns=STRESS_COLUMNS), tuple(warnings), data_version, pd.DataFrame())
    frame = _base_calendar(market, macro)
    if frame.empty:
        return StressBuildResult(pd.DataFrame(columns=STRESS_COLUMNS), ("No dates available.",), data_version, pd.DataFrame())

    market = _prepare_market(market)
    macro = _prepare_macro(macro)
    _add_market_components(frame, market)
    _add_macro_components(frame, macro)
    _score_components(frame, thresholds)
    component_coverage = _component_coverage(frame)
    missing_components = component_coverage.loc[component_coverage["observation_count"] == 0, "component"].tolist()
    for component in missing_components:
        warnings.append(f"{component}_component_missing")
    frame["stress_universe"] = universe
    frame["data_version"] = data_version
    return StressBuildResult(frame[STRESS_COLUMNS], tuple(warnings), data_version, component_coverage)


def export_financial_stress(result: StressBuildResult, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "financial_stress_daily.csv"
    parquet_path = output / "financial_stress_daily.parquet"
    coverage_csv_path = output / "financial_stress_component_coverage.csv"
    coverage_parquet_path = output / "financial_stress_component_coverage.parquet"
    result.frame.to_csv(csv_path, index=False)
    result.frame.to_parquet(parquet_path, index=False)
    result.component_coverage.to_csv(coverage_csv_path, index=False)
    result.component_coverage.to_parquet(coverage_parquet_path, index=False)
    return {"csv": csv_path, "parquet": parquet_path, "component_coverage_csv": coverage_csv_path, "component_coverage_parquet": coverage_parquet_path}


def prior_rolling_percentile(series: pd.Series, window: int = 252) -> pd.Series:
    return series.shift(1).rolling(window, min_periods=min(20, window)).apply(_last_percentile_rank, raw=True)


def _base_calendar(market: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    dates = []
    if not market.empty:
        dates.extend(pd.to_datetime(market["ts"], utc=True).dt.normalize().tolist())
    if not macro.empty:
        dates.extend(pd.to_datetime(macro["ts"], utc=True).dt.normalize().tolist())
    return pd.DataFrame({"ts": sorted(set(dates))})


def _prepare_market(market: pd.DataFrame) -> pd.DataFrame:
    if market.empty:
        return market
    working = market.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    return working.sort_values(["asset", "ts"])


def _prepare_macro(macro: pd.DataFrame) -> pd.DataFrame:
    if macro.empty:
        return macro
    working = macro.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    working["value"] = pd.to_numeric(working["value"], errors="coerce")
    return working.sort_values(["series_id", "ts"])


def _add_market_components(frame: pd.DataFrame, market: pd.DataFrame) -> None:
    for asset, prefix in (("SPX", "spx"), ("BTC", "btc"), ("DXY", "dxy"), ("Gold", "gold")):
        group = market[market.get("asset") == asset].copy() if not market.empty and "asset" in market.columns else pd.DataFrame()
        if group.empty:
            continue
        group = group.set_index("ts").sort_index()
        if prefix == "spx":
            frame["spx_drawdown_20d"] = frame["ts"].map(group.get("drawdown_20d"))
            frame["spx_drawdown_60d"] = frame["ts"].map(group.get("drawdown_60d"))
            frame["spx_realized_vol_20d"] = frame["ts"].map(group.get("realized_vol_20d"))
            frame["spx_absret_percentile_252d"] = frame["ts"].map(group.get("abs_ret_rank_252d"))
        elif prefix == "btc":
            frame["btc_drawdown_20d"] = frame["ts"].map(group.get("drawdown_20d"))
            frame["btc_realized_vol_20d"] = frame["ts"].map(group.get("realized_vol_20d"))
        elif prefix == "dxy":
            frame["dxy_abs_ret_20d"] = frame["ts"].map(pd.to_numeric(group.get("ret_20d"), errors="coerce").abs())
        elif prefix == "gold":
            frame["gold_return_20d"] = frame["ts"].map(pd.to_numeric(group.get("ret_20d"), errors="coerce"))


def _add_macro_components(frame: pd.DataFrame, macro: pd.DataFrame) -> None:
    series = {series_id: group.set_index("ts")["value"].sort_index() for series_id, group in macro.groupby("series_id")} if not macro.empty else {}
    if "VIXCLS" in series:
        vix = series["VIXCLS"]
        frame["vix_level"] = frame["ts"].map(vix)
        frame["vix_percentile_252d"] = frame["vix_level"].pipe(prior_rolling_percentile)
        frame["vix_change_5d"] = frame["vix_level"].diff(5)
    if "DGS10" in series:
        us10y = frame["ts"].map(series["DGS10"])
        frame["us10y_change_5d"] = us10y.diff(5)
        frame["us10y_change_20d"] = us10y.diff(20)
    if "DGS10" in series and "DGS2" in series:
        frame["yield_curve_10y2y"] = frame["ts"].map(series["DGS10"]) - frame["ts"].map(series["DGS2"])
    if "BAMLH0A0HYM2" in series:
        frame["hy_oas_level"] = frame["ts"].map(series["BAMLH0A0HYM2"])
        frame["hy_oas_change_20d"] = frame["hy_oas_level"].diff(20)
    if "NFCI" in series:
        frame["nfci_level"] = frame["ts"].map(series["NFCI"])


def _score_components(frame: pd.DataFrame, thresholds: dict) -> None:
    low_tail = float(thresholds.get("low_tail", 0.10))
    high_tail = float(thresholds.get("high_tail", 0.90))
    extreme_tail = float(thresholds.get("extreme_tail", 0.95))
    min_components = int(thresholds.get("min_components", 2))

    spx_drawdown = _col(frame, "spx_drawdown_20d")
    spx_absret = _col(frame, "spx_absret_percentile_252d")
    spx_vol = _col(frame, "spx_realized_vol_20d")
    spx_drawdown_threshold = _prior_rolling_quantile(spx_drawdown, low_tail)
    spx_vol_threshold = _prior_rolling_quantile(spx_vol, high_tail)
    frame["is_equity_stress"] = (
        (spx_drawdown <= spx_drawdown_threshold)
        | (spx_absret >= extreme_tail)
        | (spx_vol >= spx_vol_threshold)
    )
    frame["equity_stress_score"] = _bool_to_score(frame["is_equity_stress"], spx_vol)

    vix_level = _col(frame, "vix_level")
    vix_change = _col(frame, "vix_change_5d")
    vix_level_threshold = _prior_rolling_quantile(vix_level, high_tail)
    vix_change_threshold = _prior_rolling_quantile(vix_change, extreme_tail)
    frame["is_vol_stress"] = (vix_level >= vix_level_threshold) | (vix_change >= vix_change_threshold)
    frame["vol_stress_score"] = _bool_to_score(frame["is_vol_stress"], vix_level)

    us10y_change_5d = _col(frame, "us10y_change_5d")
    us10y_change_20d = _col(frame, "us10y_change_20d")
    rates_threshold_5d = _prior_rolling_quantile(us10y_change_5d.abs(), extreme_tail)
    rates_threshold_20d = _prior_rolling_quantile(us10y_change_20d.abs(), extreme_tail)
    frame["is_rates_stress"] = (us10y_change_5d.abs() >= rates_threshold_5d) | (us10y_change_20d.abs() >= rates_threshold_20d)
    frame["rates_stress_score"] = _bool_to_score(frame["is_rates_stress"], us10y_change_5d)

    hy_level = _col(frame, "hy_oas_level")
    hy_change = _col(frame, "hy_oas_change_20d")
    hy_level_threshold = _prior_rolling_quantile(hy_level, high_tail)
    hy_change_threshold = _prior_rolling_quantile(hy_change, extreme_tail)
    frame["is_credit_stress"] = (hy_level >= hy_level_threshold) | (hy_change >= hy_change_threshold)
    frame["credit_stress_score"] = _bool_to_score(frame["is_credit_stress"], hy_level)

    dxy_abs_ret = _col(frame, "dxy_abs_ret_20d")
    dxy_threshold = _prior_rolling_quantile(dxy_abs_ret, extreme_tail)
    frame["dollar_stress_score"] = _bool_to_score(dxy_abs_ret >= dxy_threshold, dxy_abs_ret)

    gold_return = _col(frame, "gold_return_20d")
    gold_threshold = _prior_rolling_quantile(gold_return.abs(), extreme_tail)
    frame["is_gold_stress"] = gold_return.abs() >= gold_threshold
    frame["gold_stress_score"] = _bool_to_score(frame["is_gold_stress"], gold_return)

    btc_drawdown = _col(frame, "btc_drawdown_20d")
    btc_vol = _col(frame, "btc_realized_vol_20d")
    btc_drawdown_threshold = _prior_rolling_quantile(btc_drawdown, low_tail)
    btc_vol_threshold = _prior_rolling_quantile(btc_vol, high_tail)
    frame["is_crypto_stress"] = (btc_drawdown <= btc_drawdown_threshold) | (btc_vol >= btc_vol_threshold)
    frame["crypto_stress_score"] = _bool_to_score(frame["is_crypto_stress"], btc_vol)

    component_cols = [
        "equity_stress_score",
        "vol_stress_score",
        "rates_stress_score",
        "credit_stress_score",
        "dollar_stress_score",
        "gold_stress_score",
        "crypto_stress_score",
    ]
    frame["component_count"] = frame[component_cols].notna().sum(axis=1)
    frame["cross_asset_stress_score"] = frame[component_cols].mean(axis=1, skipna=True)
    frame.loc[frame["component_count"] < min_components, "cross_asset_stress_score"] = np.nan
    frame["is_cross_asset_stress"] = frame["cross_asset_stress_score"] >= 0.5
    frame["stress_regime"] = np.where(
        frame["component_count"] < min_components,
        "insufficient_coverage",
        np.where(frame["is_cross_asset_stress"], "stress", "normal"),
    )
    for column in [col for col in STRESS_COLUMNS if col not in frame.columns]:
        frame[column] = np.nan


def _prior_rolling_quantile(series: pd.Series | None, quantile: float, window: int = 252) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(series, errors="coerce").shift(1).rolling(window, min_periods=min(20, window)).quantile(quantile)


def _col(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _bool_to_score(flag: pd.Series, coverage_series: pd.Series | None) -> pd.Series:
    score = flag.astype("boolean").map({True: 1.0, False: 0.0})
    if coverage_series is not None:
        score[pd.to_numeric(coverage_series, errors="coerce").isna()] = np.nan
    return score.astype(float)


def _last_percentile_rank(values: np.ndarray) -> float:
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return math.nan
    return float(np.mean(values <= values[-1]))


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target


def _component_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "equity_stress": "equity_stress_score",
        "vol_stress": "vol_stress_score",
        "rates_stress": "rates_stress_score",
        "credit_stress": "credit_stress_score",
        "dollar_stress": "dollar_stress_score",
        "gold_stress": "gold_stress_score",
        "crypto_stress": "crypto_stress_score",
    }
    rows = []
    for component, column in mapping.items():
        series = frame[column] if column in frame.columns else pd.Series(dtype=float)
        rows.append(
            {
                "component": component,
                "column": column,
                "observation_count": int(series.notna().sum()),
                "missing_count": int(series.isna().sum()) if len(series) else 0,
                "coverage_pct": float(series.notna().mean()) if len(series) else 0.0,
            }
        )
    return pd.DataFrame(rows)
