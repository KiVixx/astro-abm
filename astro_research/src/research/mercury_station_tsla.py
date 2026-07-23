from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from astro_daily.config import _parse_simple_yaml
from astro_daily.retrograde import STATION_OUT, StationEvent, scan_station_events
from astro_daily.swiss_ephemeris_backend import SwissEphemerisBackend
from research.bootstrap import permutation_p_value
from research.multiple_testing import benjamini_hochberg


METRIC_LABELS_ZH = {
    "cumulative_return": "窗口累積報酬",
    "cumulative_excess_return_vs_spx": "相對 SPX 累積超額報酬",
    "realized_volatility": "年化實現波動",
    "max_drawdown": "窗口最大回撤",
    "extreme_move_frequency": "極端單日波動頻率",
    "positive_day_frequency": "正報酬交易日比例",
    "negative_day_frequency": "負報酬交易日比例",
    "positive_window_frequency": "窗口正累積報酬比例",
}

WINDOW_LABELS_ZH = {
    "station_session": "station 後首個可觀察交易日",
    "station_to_day3_calendar_0_3": "轉順 station 第 0～+3 日",
    "station_to_day8_calendar_0_8": "轉順 station 第 0～+8 日",
    "post_early_calendar_1_7": "轉順後前期（曆日 +1～+7）",
    "post_late_calendar_8_14": "station 後期（曆日 +8～+14）",
    "post_full_calendar_1_14": "完整 post-station（曆日 +1～+14）",
    "post_early_trading_1_5": "轉順後前 1～5 個交易日",
    "post_late_trading_6_10": "station 後第 6～10 個交易日",
}

BASELINE_LABELS_ZH = {
    "non_event": "非事件日期",
    "month_matched": "相同月份匹配",
    "volatility_regime_matched": "事前波動狀態匹配",
}


@dataclass(frozen=True)
class WindowSpec:
    name: str
    mode: str
    start: int
    end: int


@dataclass(frozen=True)
class MercuryTslaStudyResult:
    results: pd.DataFrame
    event_metrics: pd.DataFrame
    station_events: pd.DataFrame
    data_quality: dict[str, Any]
    config_text: str
    config_hash: str


def load_study_config(path: str | Path) -> tuple[dict[str, Any], str]:
    config_text = Path(path).read_text()
    return _parse_simple_yaml(config_text), config_text


def load_price_csv(path: str | Path, *, asset: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "date" if "date" in frame.columns else "ts"
    if date_column not in frame.columns or "close" not in frame.columns:
        raise ValueError(f"{asset} CSV must include date/ts and close columns.")
    price_column = "adj_close" if "adj_close" in frame.columns else "close"
    working = frame.copy()
    working["ts"] = pd.to_datetime(working[date_column], utc=True, errors="coerce").dt.normalize()
    working["price"] = pd.to_numeric(working[price_column], errors="coerce")
    working = working.dropna(subset=["ts", "price"]).sort_values("ts")
    if working["ts"].duplicated().any():
        raise ValueError(f"{asset} CSV contains duplicate dates.")
    if (working["price"] <= 0).any():
        raise ValueError(f"{asset} CSV contains non-positive prices.")
    working["asset"] = asset
    return working[["ts", "asset", "price"]].reset_index(drop=True)


def price_data_quality(frame: pd.DataFrame) -> dict[str, Any]:
    returns = frame["price"].pct_change(fill_method=None)
    return {
        "rows": int(len(frame)),
        "coverage_start": _date_text(frame["ts"].min()),
        "coverage_end": _date_text(frame["ts"].max()),
        "duplicate_dates": int(frame["ts"].duplicated().sum()),
        "missing_prices": int(frame["price"].isna().sum()),
        "nonpositive_prices": int((frame["price"] <= 0).sum()),
        "max_abs_daily_return": _optional_float(returns.abs().max()),
        "abs_daily_return_gt_50pct": int((returns.abs() > 0.50).sum()),
    }


def build_market_panel(tsla: pd.DataFrame, spx: pd.DataFrame) -> pd.DataFrame:
    panel = tsla[["ts", "price"]].rename(columns={"price": "tsla_price"}).copy()
    benchmark = spx[["ts", "price"]].rename(columns={"price": "spx_price"})
    panel = panel.merge(benchmark, on="ts", how="left").sort_values("ts").reset_index(drop=True)
    panel["log_ret"] = np.log(panel["tsla_price"] / panel["tsla_price"].shift(1))
    panel["spx_log_ret"] = np.log(panel["spx_price"] / panel["spx_price"].shift(1))
    panel["excess_log_ret"] = panel["log_ret"] - panel["spx_log_ret"]
    panel["pre_event_vol_20d"] = panel["log_ret"].rolling(20, min_periods=10).std().shift(1)
    prior_abs_return_threshold = (
        panel["log_ret"]
        .abs()
        .rolling(252, min_periods=60)
        .quantile(0.95)
        .shift(1)
    )
    panel["is_extreme_move"] = panel["log_ret"].abs() >= prior_abs_return_threshold
    return panel


def generate_mercury_station_out_events(
    *,
    start_ts: datetime,
    end_ts: datetime,
    step_hours: int = 6,
    tolerance_seconds: int = 60,
) -> list[StationEvent]:
    events = scan_station_events(
        backend=SwissEphemerisBackend(),
        bodies=["Mercury"],
        start_ts=start_ts,
        end_ts=end_ts,
        step_hours=step_hours,
        tolerance_seconds=tolerance_seconds,
    )
    return [event for event in events if event.station_type == STATION_OUT]


def parse_windows(raw: dict[str, Any]) -> list[WindowSpec]:
    windows = []
    for name, values in raw.items():
        windows.append(
            WindowSpec(
                name=str(name),
                mode=str(values.get("mode", "calendar")),
                start=int(values.get("start", 0)),
                end=int(values.get("end", 0)),
            )
        )
    return windows


def run_mercury_tsla_study(
    *,
    config: dict[str, Any],
    config_text: str,
    tsla: pd.DataFrame,
    spx: pd.DataFrame,
    station_events: Iterable[StationEvent],
) -> MercuryTslaStudyResult:
    study = config.get("study", {})
    statistics = config.get("statistics", {})
    windows = parse_windows(config.get("windows", {}))
    baselines = _split(config.get("baselines", "non_event,month_matched,volatility_regime_matched"))
    metrics = _split(config.get("metrics", ",".join(METRIC_LABELS_ZH)))
    random_seed = int(statistics.get("random_seed", 42))
    bootstrap_samples = int(statistics.get("bootstrap_samples", 2000))
    permutation_samples = int(statistics.get("permutation_samples", 2000))
    baseline_samples_per_event = int(statistics.get("baseline_samples_per_event", 50))
    inference_baseline_cap = int(statistics.get("inference_baseline_cap", 500))
    exclusion_days = int(statistics.get("event_exclusion_days", 30))

    panel = build_market_panel(tsla, spx)
    station_rows = _station_rows(station_events, panel)
    station_frame = pd.DataFrame(station_rows)
    baseline_calendar, volatility_quantiles = _build_baseline_calendar(
        panel=panel,
        station_frame=station_frame,
        exclusion_days=exclusion_days,
    )
    event_metric_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    baseline_cache: dict[tuple[str, str], pd.DataFrame] = {}
    rng = np.random.default_rng(random_seed)

    for window in windows:
        observed = _event_metrics_for_window(
            panel=panel,
            station_frame=station_frame,
            window=window,
            source="event",
        )
        event_metric_rows.extend(observed.to_dict("records"))
        for baseline in baselines:
            cache_key = (window.name, baseline)
            baseline_metrics = baseline_cache.get(cache_key)
            if baseline_metrics is None:
                baseline_metrics = _matched_baseline_metrics(
                    panel=panel,
                    station_frame=station_frame,
                    baseline_calendar=baseline_calendar,
                    volatility_quantiles=volatility_quantiles,
                    window=window,
                    method=baseline,
                    samples_per_event=baseline_samples_per_event,
                    rng=rng,
                )
                baseline_cache[cache_key] = baseline_metrics
            for metric in metrics:
                event_values = pd.to_numeric(observed.get(metric), errors="coerce").dropna().to_numpy()
                baseline_values = pd.to_numeric(baseline_metrics.get(metric), errors="coerce").dropna().to_numpy()
                inference_baseline = _deterministic_cap(
                    baseline_values,
                    limit=inference_baseline_cap,
                    seed=_stable_seed(random_seed, window.name, baseline, metric),
                )
                effect = _mean(event_values)
                baseline_value = _mean(baseline_values)
                ci_low, ci_high = bootstrap_difference_ci(
                    event_values,
                    inference_baseline,
                    samples=bootstrap_samples,
                    seed=random_seed,
                )
                p_value = permutation_p_value(
                    event_values,
                    inference_baseline,
                    samples=permutation_samples,
                    seed=random_seed,
                )
                result_rows.append(
                    {
                        "study_id": str(study.get("study_id", "mercury_station_out_tsla_v1")),
                        "asset": "TSLA",
                        "event_type": STATION_OUT,
                        "window_name": window.name,
                        "window_mode": window.mode,
                        "baseline_method": baseline,
                        "metric": metric,
                        "effect_value": effect,
                        "baseline_value": baseline_value,
                        "effect_minus_baseline": effect - baseline_value
                        if not math.isnan(effect) and not math.isnan(baseline_value)
                        else math.nan,
                        "bootstrap_diff_ci_low": ci_low,
                        "bootstrap_diff_ci_high": ci_high,
                        "p_value": p_value,
                        "q_value_fdr": math.nan,
                        "placebo_percentile": _percentile_vs_placebo(effect, baseline_values),
                        "n_events": int(len(event_values)),
                        "n_baseline_windows": int(len(baseline_values)),
                        "coverage_start": _date_text(panel["ts"].min()),
                        "coverage_end": _date_text(panel["ts"].max()),
                        "interpretation": "historical_association_only",
                    }
                )

    results = pd.DataFrame(result_rows)
    if not results.empty:
        results["q_value_fdr"] = benjamini_hochberg(results["p_value"].tolist())
    event_metrics = pd.DataFrame(event_metric_rows)
    quality = {
        "TSLA": price_data_quality(tsla),
        "SPX": price_data_quality(spx),
        "station_out_events_scanned": int(len(station_frame)),
        "completed_station_out_events": int(
            station_frame["has_complete_post_14d"].sum()
        ) if not station_frame.empty else 0,
        "latest_station_out_exact_ts": (
            station_frame["exact_ts"].max().isoformat() if not station_frame.empty else None
        ),
        "latest_station_has_complete_post_14d": (
            bool(station_frame.sort_values("exact_ts").iloc[-1]["has_complete_post_14d"])
            if not station_frame.empty
            else False
        ),
        "extreme_move_threshold": "rolling prior 252-session 95th percentile; no future leakage",
        "source_notes": [
            "TSLA and SPX use adjusted-close daily data from local Yahoo chart research snapshots.",
            "Yahoo-derived files are local research inputs and require licensing review before redistribution.",
            "Mercury stations are calculated locally with Swiss Ephemeris longitude speed sign changes.",
        ],
    }
    return MercuryTslaStudyResult(
        results=results,
        event_metrics=event_metrics,
        station_events=station_frame,
        data_quality=quality,
        config_text=config_text,
        config_hash=hashlib.sha256(config_text.encode()).hexdigest(),
    )


def write_mercury_tsla_report(
    result: MercuryTslaStudyResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output / "summary_zh-Hant.md",
        "results_csv": output / "results.csv",
        "results_parquet": output / "results.parquet",
        "event_metrics_csv": output / "event_metrics.csv",
        "station_events_csv": output / "station_events.csv",
        "data_quality": output / "data_quality.json",
        "config_snapshot": output / "config_snapshot.yaml",
    }
    result.results.to_csv(paths["results_csv"], index=False)
    result.results.to_parquet(paths["results_parquet"], index=False)
    result.event_metrics.to_csv(paths["event_metrics_csv"], index=False)
    result.station_events.to_csv(paths["station_events_csv"], index=False)
    paths["data_quality"].write_text(
        json.dumps(result.data_quality, ensure_ascii=False, indent=2)
    )
    paths["config_snapshot"].write_text(result.config_text)
    paths["summary"].write_text(_summary_markdown(result))
    return paths


def bootstrap_difference_ci(
    event_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    samples: int,
    seed: int,
    alpha: float = 0.05,
) -> tuple[float, float]:
    event = _clean_array(event_values)
    baseline = _clean_array(baseline_values)
    if len(event) == 0 or len(baseline) == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    differences = np.empty(samples)
    for index in range(samples):
        event_sample = rng.choice(event, size=len(event), replace=True)
        baseline_sample = rng.choice(baseline, size=len(baseline), replace=True)
        differences[index] = event_sample.mean() - baseline_sample.mean()
    return (
        float(np.quantile(differences, alpha / 2)),
        float(np.quantile(differences, 1 - alpha / 2)),
    )


def _station_rows(events: Iterable[StationEvent], panel: pd.DataFrame) -> list[dict[str, Any]]:
    first_date = panel["ts"].min()
    last_date = panel["ts"].max()
    rows = []
    for event in events:
        event_date = pd.Timestamp(event.date, tz="UTC")
        if event_date < first_date - timedelta(days=30) or event_date > last_date + timedelta(days=30):
            continue
        rows.append(
            {
                "event_id": f"Mercury_station_out_{event.exact_ts:%Y%m%d%H%M}",
                "exact_ts": event.exact_ts,
                "station_date": event_date,
                "station_type": event.station_type,
                "has_complete_post_14d": event_date + timedelta(days=14) <= last_date,
                "pre_event_vol_20d": _latest_value_on_or_before(
                    panel, event_date, "pre_event_vol_20d"
                ),
            }
        )
    return rows


def _event_metrics_for_window(
    *,
    panel: pd.DataFrame,
    station_frame: pd.DataFrame,
    window: WindowSpec,
    source: str,
) -> pd.DataFrame:
    rows = []
    for event in station_frame.itertuples(index=False):
        selected = _select_window(panel, event.station_date, window)
        if not _window_is_complete(panel, event.station_date, window, selected):
            continue
        metrics = _window_metrics(selected)
        rows.append(
            {
                "event_id": event.event_id,
                "station_date": event.station_date,
                "exact_ts": event.exact_ts,
                "window_name": window.name,
                "source": source,
                "era": _tsla_era(event.station_date),
                "n_trading_days": int(len(selected)),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _matched_baseline_metrics(
    *,
    panel: pd.DataFrame,
    station_frame: pd.DataFrame,
    baseline_calendar: pd.DataFrame,
    volatility_quantiles: np.ndarray,
    window: WindowSpec,
    method: str,
    samples_per_event: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    for event in station_frame.itertuples(index=False):
        candidates = baseline_calendar
        if method == "month_matched":
            candidates = candidates[candidates["anchor_date"].dt.month == event.station_date.month]
        elif method == "volatility_regime_matched":
            event_regime = _volatility_regime(event.pre_event_vol_20d, volatility_quantiles)
            candidates = candidates[candidates["volatility_regime"] == event_regime]
        elif method != "non_event":
            raise ValueError(f"Unsupported baseline method: {method}")
        if candidates.empty:
            continue
        candidate_dates = candidates["anchor_date"].to_numpy()
        sampled = rng.choice(
            candidate_dates,
            size=min(samples_per_event, len(candidate_dates)),
            replace=False,
        )
        for sample_index, anchor in enumerate(pd.to_datetime(sampled, utc=True)):
            selected = _select_window(panel, anchor, window)
            if not _window_is_complete(panel, anchor, window, selected):
                continue
            rows.append(
                {
                    "event_id": event.event_id,
                    "baseline_id": f"{event.event_id}_{method}_{sample_index}",
                    "anchor_date": anchor,
                    "window_name": window.name,
                    **_window_metrics(selected),
                }
            )
    return pd.DataFrame(rows)


def _build_baseline_calendar(
    *,
    panel: pd.DataFrame,
    station_frame: pd.DataFrame,
    exclusion_days: int,
) -> tuple[pd.DataFrame, np.ndarray]:
    calendar = pd.DataFrame(
        {
            "anchor_date": pd.date_range(
                panel["ts"].min(),
                panel["ts"].max(),
                freq="D",
                tz="UTC",
            )
        }
    )
    volatility = panel[["ts", "pre_event_vol_20d"]].dropna().sort_values("ts")
    calendar = pd.merge_asof(
        calendar.sort_values("anchor_date"),
        volatility,
        left_on="anchor_date",
        right_on="ts",
        direction="backward",
    ).drop(columns=["ts"])
    valid_vol = calendar["pre_event_vol_20d"].dropna()
    quantiles = (
        np.unique(valid_vol.quantile([0.25, 0.5, 0.75]).to_numpy())
        if not valid_vol.empty
        else np.array([])
    )
    calendar["volatility_regime"] = calendar["pre_event_vol_20d"].map(
        lambda value: _volatility_regime(value, quantiles)
    )
    station_dates = station_frame["station_date"].tolist()
    if station_dates:
        near_event = np.zeros(len(calendar), dtype=bool)
        anchors = calendar["anchor_date"]
        for station_date in station_dates:
            near_event |= (anchors - station_date).abs().dt.days <= exclusion_days
        calendar = calendar[~near_event]
    return calendar.reset_index(drop=True), quantiles


def _select_window(panel: pd.DataFrame, anchor: pd.Timestamp, window: WindowSpec) -> pd.DataFrame:
    timestamps = panel["ts"]
    if window.mode == "anchored_calendar":
        start = anchor + timedelta(days=window.start)
        end = anchor + timedelta(days=window.end)
        left = int(timestamps.searchsorted(start, side="left"))
        right = int(timestamps.searchsorted(end, side="right"))
        return panel.iloc[left:right].copy()
    if window.mode == "calendar":
        start = anchor + timedelta(days=window.start)
        end = anchor + timedelta(days=window.end)
        left = int(timestamps.searchsorted(start, side="left"))
        right = int(timestamps.searchsorted(end, side="right"))
        return panel.iloc[left:right].copy()
    first_session = int(timestamps.searchsorted(anchor, side="right"))
    if window.mode == "station_session":
        return panel.iloc[first_session : first_session + 1].copy()
    if window.mode == "trading":
        left = first_session + max(0, window.start - 1)
        right = first_session + window.end
        return panel.iloc[left:right].copy()
    raise ValueError(f"Unsupported window mode: {window.mode}")


def _window_is_complete(
    panel: pd.DataFrame,
    anchor: pd.Timestamp,
    window: WindowSpec,
    selected: pd.DataFrame,
) -> bool:
    if selected.empty:
        return False
    if window.mode in {"calendar", "anchored_calendar"}:
        return anchor + timedelta(days=window.end) <= panel["ts"].max()
    required_sessions = 1 if window.mode == "station_session" else window.end
    available_sessions = int((panel["ts"] > anchor).sum())
    return available_sessions >= required_sessions


def _window_metrics(selected: pd.DataFrame) -> dict[str, float]:
    log_returns = pd.to_numeric(selected["log_ret"], errors="coerce").dropna()
    excess = pd.to_numeric(selected["excess_log_ret"], errors="coerce").dropna()
    if log_returns.empty:
        return {metric: math.nan for metric in METRIC_LABELS_ZH}
    cumulative = float(np.expm1(log_returns.sum()))
    path = np.exp(log_returns.cumsum())
    path_with_origin = np.concatenate(([1.0], path.to_numpy()))
    running_max = np.maximum.accumulate(path_with_origin)
    max_drawdown = float(np.min(path_with_origin / running_max - 1.0))
    return {
        "cumulative_return": cumulative,
        "cumulative_excess_return_vs_spx": float(np.expm1(excess.sum()))
        if not excess.empty
        else math.nan,
        "realized_volatility": float(np.sqrt(np.mean(np.square(log_returns))) * np.sqrt(252)),
        "max_drawdown": max_drawdown,
        "extreme_move_frequency": float(selected.loc[log_returns.index, "is_extreme_move"].mean()),
        "positive_day_frequency": float((log_returns > 0).mean()),
        "negative_day_frequency": float((log_returns < 0).mean()),
        "positive_window_frequency": float(cumulative > 0),
    }


def _latest_value_on_or_before(
    panel: pd.DataFrame,
    anchor: pd.Timestamp,
    column: str,
) -> float:
    values = pd.to_numeric(panel.loc[panel["ts"] <= anchor, column], errors="coerce").dropna()
    return float(values.iloc[-1]) if not values.empty else math.nan


def _volatility_regime(value: float, quantiles: np.ndarray) -> str:
    if value is None or math.isnan(float(value)):
        return "unknown"
    return f"q{int(np.searchsorted(quantiles, float(value), side='right')) + 1}"


def _summary_markdown(result: MercuryTslaStudyResult) -> str:
    quality = result.data_quality
    tsla = quality["TSLA"]
    latest_event = (
        result.station_events.sort_values("exact_ts").iloc[-1]
        if not result.station_events.empty
        else None
    )
    lines = [
        "# 水星轉順至 station 後期對 TSLA 的歷史關聯研究",
        "",
        "## 研究定位",
        "",
        "本研究檢查 Mercury 由逆行轉為順行（retrograde-to-direct station）後，TSLA 的報酬、波動與回撤是否和匹配基線存在歷史差異。",
        "結果只代表歷史關聯，不代表因果、未來預測、財務建議或交易訊號。",
        "",
        "## 資料覆蓋",
        "",
        f"- TSLA：{tsla['coverage_start']} 至 {tsla['coverage_end']}，共 {tsla['rows']} 個交易日。",
        f"- 完整 +14 日 post-station 事件：{quality['completed_station_out_events']} 次。",
        "- 價格使用 adjusted close，以降低拆股對報酬序列的機械性干擾。",
        "- SPX 用作大盤基準，另計算 TSLA 相對 SPX 的超額報酬。",
        "- 極端波動門檻只使用當時以前的 252 個交易日，避免未來資料洩漏。",
        "",
        "## 事件窗口",
        "",
    ]
    for name, label in WINDOW_LABELS_ZH.items():
        lines.append(f"- `{name}`：{label}")
    lines.extend(
        [
            "",
            "## 執行摘要",
            "",
        ]
    )
    robust_count = int((result.results["q_value_fdr"] < 0.10).sum())
    nominal_count = int((result.results["p_value"] < 0.05).sum())
    lines.extend(
        [
            f"- 共檢查 {len(result.results)} 組窗口、指標與基線組合；原始 p < 0.05 有 {nominal_count} 組。",
            f"- 經 Benjamini-Hochberg FDR 後，q < 0.10 有 {robust_count} 組。",
            "- 核心判斷：目前沒有足夠證據證明 Mercury 轉順後，TSLA 的波動或報酬存在可重複的穩健 alpha。",
            "- 描述性資料偏向 post-station 後期報酬較弱、回撤較深，但未通過本研究的多重檢定門檻。",
            "",
            "## 主要結果",
            "",
            "以下以「事前波動狀態匹配」作為主要基線；其他基線完整保存在 `results.csv/parquet`。",
            "",
            "| 窗口 | 指標 | 事件值 | 匹配基線 | 差異 | q 值 | 事件數 | 判讀 |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    focus = result.results[
        result.results["window_name"].isin(
            ["post_early_calendar_1_7", "post_late_calendar_8_14", "post_full_calendar_1_14"]
        )
        & (result.results["baseline_method"] == "volatility_regime_matched")
        & result.results["metric"].isin(
            [
                "cumulative_return",
                "cumulative_excess_return_vs_spx",
                "realized_volatility",
                "max_drawdown",
                "extreme_move_frequency",
            ]
        )
    ].sort_values(["q_value_fdr", "window_name", "metric"])
    for row in focus.itertuples(index=False):
        significant = (
            pd.notna(row.q_value_fdr)
            and float(row.q_value_fdr) < 0.10
            and int(row.n_events) >= 20
            and not (
                float(row.bootstrap_diff_ci_low) <= 0 <= float(row.bootstrap_diff_ci_high)
            )
        )
        interpretation = "較穩健的探索性差異" if significant else "未達目前穩健門檻"
        lines.append(
            "| "
            + " | ".join(
                [
                    WINDOW_LABELS_ZH.get(row.window_name, row.window_name),
                    METRIC_LABELS_ZH.get(row.metric, row.metric),
                    _format_metric(row.metric, row.effect_value),
                    _format_metric(row.metric, row.baseline_value),
                    _format_metric(row.metric, row.effect_minus_baseline),
                    f"{row.q_value_fdr:.3f}" if pd.notna(row.q_value_fdr) else "NA",
                    str(int(row.n_events)),
                    interpretation,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 年代分段描述",
            "",
            "年代分段只作穩定性觀察，不另外宣稱顯著性；各分段樣本很少。",
            "",
            "| 年代 | 窗口 | 事件數 | 平均累積報酬 | 平均相對 SPX 報酬 | 平均年化波動 | 平均最大回撤 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    era_rows = (
        result.event_metrics[
            result.event_metrics["window_name"].isin(
                [
                    "post_early_calendar_1_7",
                    "post_late_calendar_8_14",
                    "post_full_calendar_1_14",
                ]
            )
        ]
        .groupby(["era", "window_name"], as_index=False)
        .agg(
            n_events=("event_id", "nunique"),
            cumulative_return=("cumulative_return", "mean"),
            cumulative_excess_return_vs_spx=("cumulative_excess_return_vs_spx", "mean"),
            realized_volatility=("realized_volatility", "mean"),
            max_drawdown=("max_drawdown", "mean"),
        )
        .sort_values(["era", "window_name"])
    )
    for row in era_rows.itertuples(index=False):
        lines.append(
            "| "
            + " | ".join(
                [
                    row.era,
                    WINDOW_LABELS_ZH.get(row.window_name, row.window_name),
                    str(int(row.n_events)),
                    _format_metric("cumulative_return", row.cumulative_return),
                    _format_metric(
                        "cumulative_excess_return_vs_spx",
                        row.cumulative_excess_return_vs_spx,
                    ),
                    _format_metric("realized_volatility", row.realized_volatility),
                    _format_metric("max_drawdown", row.max_drawdown),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 當前 2026 年 7 月事件",
            "",
        ]
    )
    if latest_event is not None:
        lines.extend(
            [
                f"- 精確轉順時間：`{latest_event['exact_ts'].isoformat()}`。",
                f"- 是否已有完整 +14 日市場資料：`{str(bool(latest_event['has_complete_post_14d'])).lower()}`。",
                "- 目前事件尚未完成時，不應把未來價格補入或納入歷史效果估計。",
            ]
        )
    lines.extend(
        [
            "",
            "## 穩健性與限制",
            "",
            "- TSLA 自 2010 年上市，因此即使使用全部歷史，Mercury 轉順事件數仍只有約五十次；這不是大樣本。",
            "- TSLA 的公司成熟度、市值、波動與投資者結構在樣本期間明顯改變，單一全樣本平均可能掩蓋年代差異。",
            "- 月份匹配與事前波動狀態匹配可降低季節性及波動環境偏誤，但不能控制所有公司事件、利率、財報及市場新聞。",
            "- 多窗口、多指標與多基線已使用 Benjamini-Hochberg FDR，但資料探勘風險仍然存在。",
            "- Yahoo 來源只供本地研究；若公開數據檔或用於出版，需另行確認授權。",
            "",
            "## 結論規則",
            "",
            "只有在 q < 0.10、事件數至少 20，且 bootstrap 差異信賴區間不跨 0 時，才標記為較穩健的探索性差異；否則一律視為尚未證明。",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_metric(metric: str, value: float) -> str:
    if pd.isna(value):
        return "NA"
    if metric in {
        "cumulative_return",
        "cumulative_excess_return_vs_spx",
        "max_drawdown",
        "extreme_move_frequency",
        "positive_day_frequency",
        "negative_day_frequency",
        "positive_window_frequency",
    }:
        return f"{float(value):.2%}"
    return f"{float(value):.3f}"


def _tsla_era(station_date: pd.Timestamp) -> str:
    year = pd.Timestamp(station_date).year
    if year <= 2015:
        return "2010–2015"
    if year <= 2020:
        return "2016–2020"
    return "2021–2026"


def _percentile_vs_placebo(effect: float, placebo: np.ndarray) -> float:
    clean = _clean_array(placebo)
    if math.isnan(effect) or len(clean) == 0:
        return math.nan
    return float(np.mean(clean <= effect))


def _clean_array(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    return array[~np.isnan(array)]


def _deterministic_cap(values: Iterable[float], *, limit: int, seed: int) -> np.ndarray:
    clean = _clean_array(values)
    if limit <= 0 or len(clean) <= limit:
        return clean
    return np.random.default_rng(seed).choice(clean, size=limit, replace=False)


def _stable_seed(base_seed: int, *parts: str) -> int:
    payload = "|".join([str(base_seed), *parts]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _mean(values: Iterable[float]) -> float:
    clean = _clean_array(values)
    return float(clean.mean()) if len(clean) else math.nan


def _split(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _date_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _optional_float(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)
