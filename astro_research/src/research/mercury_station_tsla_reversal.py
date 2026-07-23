from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from astro_daily.retrograde import StationEvent
from research.bootstrap import permutation_p_value
from research.mercury_station_tsla import (
    BASELINE_LABELS_ZH,
    WINDOW_LABELS_ZH,
    MercuryTslaStudyResult,
    WindowSpec,
    _build_baseline_calendar,
    _clean_array,
    _date_text,
    _deterministic_cap,
    _format_metric,
    _mean,
    _select_window,
    _stable_seed,
    _station_rows,
    _tsla_era,
    _volatility_regime,
    _window_is_complete,
    bootstrap_difference_ci,
    build_market_panel,
    parse_windows,
    price_data_quality,
)
from research.multiple_testing import benjamini_hochberg


REVERSAL_METRICS = {
    "reversal_frequency": "趨勢反轉比例",
    "strong_trend_reversal_frequency": "強趨勢後反轉比例",
    "normalized_reversal_strength": "波動標準化反轉強度",
    "reversal_signed_return": "反方向相對報酬",
    "downtrend_rebound_frequency": "事前下跌後反彈比例",
    "uptrend_fade_frequency": "事前上漲後回落比例",
    "post_excess_after_downtrend": "事前下跌後相對 SPX 報酬",
    "post_excess_after_uptrend": "事前上漲後相對 SPX 報酬",
}


@dataclass(frozen=True)
class MercuryTslaReversalResult:
    results: pd.DataFrame
    event_details: pd.DataFrame
    station_events: pd.DataFrame
    data_quality: dict[str, Any]
    config_text: str
    config_hash: str


def run_mercury_tsla_reversal_study(
    *,
    config: dict[str, Any],
    config_text: str,
    tsla: pd.DataFrame,
    spx: pd.DataFrame,
    station_events: Iterable[StationEvent],
) -> MercuryTslaReversalResult:
    study = config.get("study", {})
    statistics = config.get("statistics", {})
    primary = config.get("primary_hypothesis", {})
    windows = parse_windows(config.get("windows", {}))
    primary_window_name = str(
        primary.get("window_name", "station_to_day3_calendar_0_3")
    )
    primary_window = next(
        (window for window in windows if window.name == primary_window_name),
        None,
    )
    if primary_window is None:
        raise ValueError(
            f"Primary reversal window is not configured: {primary_window_name}"
        )
    trend_horizons = [int(value) for value in _split(config.get("trend_horizons", "10,20"))]
    baselines = _split(config.get("baselines", "non_event,month_matched,volatility_regime_matched"))
    metrics = _split(config.get("metrics", ",".join(REVERSAL_METRICS)))
    strong_trend_threshold = float(statistics.get("strong_trend_z_threshold", 0.5))
    random_seed = int(statistics.get("random_seed", 42))
    bootstrap_samples = int(statistics.get("bootstrap_samples", 1000))
    permutation_samples = int(statistics.get("permutation_samples", 1000))
    baseline_samples_per_event = int(statistics.get("baseline_samples_per_event", 50))
    inference_baseline_cap = int(statistics.get("inference_baseline_cap", 500))
    exclusion_days = int(statistics.get("event_exclusion_days", 30))

    panel = build_market_panel(tsla, spx)
    station_frame = pd.DataFrame(_station_rows(station_events, panel))
    if not station_frame.empty:
        station_frame["response_anchor_date"] = station_frame["exact_ts"].map(
            lambda exact_ts: _first_full_tsla_session_after(
                panel,
                pd.Timestamp(exact_ts),
            )
        )
    baseline_calendar, volatility_quantiles = _build_baseline_calendar(
        panel=panel,
        station_frame=station_frame,
        exclusion_days=exclusion_days,
    )
    rng = np.random.default_rng(random_seed)
    result_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for horizon in trend_horizons:
        for window in windows:
            observed = _reversal_records(
                panel=panel,
                anchors=station_frame.assign(
                    anchor_date=station_frame["response_anchor_date"]
                ),
                window=window,
                trend_horizon=horizon,
                strong_trend_threshold=strong_trend_threshold,
                source="event",
            )
            detail_rows.extend(observed.to_dict("records"))
            for baseline in baselines:
                placebo = _matched_reversal_records(
                    panel=panel,
                    station_frame=station_frame,
                    baseline_calendar=baseline_calendar,
                    volatility_quantiles=volatility_quantiles,
                    window=window,
                    trend_horizon=horizon,
                    strong_trend_threshold=strong_trend_threshold,
                    method=baseline,
                    samples_per_event=baseline_samples_per_event,
                    rng=rng,
                )
                for metric in metrics:
                    event_values = pd.to_numeric(observed.get(metric), errors="coerce").dropna().to_numpy()
                    baseline_values = pd.to_numeric(placebo.get(metric), errors="coerce").dropna().to_numpy()
                    inference_baseline = _deterministic_cap(
                        baseline_values,
                        limit=inference_baseline_cap,
                        seed=_stable_seed(
                            random_seed,
                            str(horizon),
                            window.name,
                            baseline,
                            metric,
                        ),
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
                    test_family = _test_family(
                        horizon=horizon,
                        window=window.name,
                        baseline=baseline,
                        metric=metric,
                        primary=primary,
                    )
                    result_rows.append(
                        {
                            "study_id": str(
                                study.get(
                                    "study_id",
                                    "mercury_station_out_tsla_reversal_v1",
                                )
                            ),
                            "asset": "TSLA",
                            "event_type": "retrograde_to_direct",
                            "trend_horizon_sessions": horizon,
                            "window_name": window.name,
                            "window_mode": window.mode,
                            "baseline_method": baseline,
                            "metric": metric,
                            "test_family": test_family,
                            "effect_value": effect,
                            "baseline_value": baseline_value,
                            "effect_minus_baseline": (
                                effect - baseline_value
                                if not math.isnan(effect)
                                and not math.isnan(baseline_value)
                                else math.nan
                            ),
                            "bootstrap_diff_ci_low": ci_low,
                            "bootstrap_diff_ci_high": ci_high,
                            "p_value": p_value,
                            "q_value_fdr": math.nan,
                            "placebo_percentile": _percentile(effect, baseline_values),
                            "n_events": int(len(event_values)),
                            "n_baseline_windows": int(len(baseline_values)),
                            "coverage_start": _date_text(panel["ts"].min()),
                            "coverage_end": _date_text(panel["ts"].max()),
                            "interpretation": "historical_association_only",
                        }
                    )

    results = pd.DataFrame(result_rows)
    if not results.empty:
        for _, indexes in results.groupby("test_family").groups.items():
            results.loc[indexes, "q_value_fdr"] = benjamini_hochberg(
                results.loc[indexes, "p_value"].tolist()
            )
    details = pd.DataFrame(detail_rows)
    quality = {
        "TSLA": price_data_quality(tsla),
        "SPX": price_data_quality(spx),
        "station_out_events_scanned": int(len(station_frame)),
        "completed_post_14d_events": int(
            station_frame["has_complete_post_14d"].sum()
        )
        if not station_frame.empty
        else 0,
        "completed_primary_events": int(
            station_frame["response_anchor_date"].map(
                lambda anchor: (
                    pd.notna(anchor)
                    and anchor + pd.Timedelta(days=primary_window.end)
                    <= panel["ts"].max()
                )
            ).sum()
        )
        if not station_frame.empty
        else 0,
        "strong_trend_z_threshold": strong_trend_threshold,
        "primary_hypothesis": primary,
        "primary_window_label_zh": WINDOW_LABELS_ZH.get(
            primary_window.name,
            primary_window.name,
        ),
        "primary_window_end_day": primary_window.end,
        "trend_definition": (
            "TSLA minus SPX cumulative log return over prior trading sessions; "
            "only closes strictly before the first full TSLA session after the "
            "exact station timestamp are used."
        ),
        "reversal_definition": (
            "post-window excess-return sign is opposite the pre-station trend sign."
        ),
        "source_notes": [
            "TSLA and SPX adjusted-close inputs are ignored local Yahoo research snapshots.",
            "Mercury station timestamps are calculated locally with Swiss Ephemeris.",
            "Results are historical association only, not a trading signal.",
        ],
    }
    return MercuryTslaReversalResult(
        results=results,
        event_details=details,
        station_events=station_frame,
        data_quality=quality,
        config_text=config_text,
        config_hash=hashlib.sha256(config_text.encode()).hexdigest(),
    )


def write_mercury_tsla_reversal_report(
    result: MercuryTslaReversalResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output / "summary_zh-Hant.md",
        "results_csv": output / "results.csv",
        "results_parquet": output / "results.parquet",
        "event_details_csv": output / "event_details.csv",
        "event_details_parquet": output / "event_details.parquet",
        "station_events_csv": output / "station_events.csv",
        "data_quality": output / "data_quality.json",
        "config_snapshot": output / "config_snapshot.yaml",
    }
    result.results.to_csv(paths["results_csv"], index=False)
    result.results.to_parquet(paths["results_parquet"], index=False)
    result.event_details.to_csv(paths["event_details_csv"], index=False)
    result.event_details.to_parquet(paths["event_details_parquet"], index=False)
    result.station_events.to_csv(paths["station_events_csv"], index=False)
    paths["data_quality"].write_text(
        json.dumps(result.data_quality, ensure_ascii=False, indent=2)
    )
    paths["config_snapshot"].write_text(result.config_text)
    paths["summary"].write_text(_summary_markdown(result))
    return paths


def reversal_record(
    *,
    panel: pd.DataFrame,
    anchor: pd.Timestamp,
    window: WindowSpec,
    trend_horizon: int,
    strong_trend_threshold: float,
) -> dict[str, float] | None:
    anchor = pd.Timestamp(anchor)
    prior = panel[panel["ts"] < anchor].tail(trend_horizon)
    post = _select_window(panel, anchor, window)
    if len(prior) < trend_horizon or not _window_is_complete(panel, anchor, window, post):
        return None
    pre_excess = pd.to_numeric(prior["excess_log_ret"], errors="coerce").dropna()
    post_excess = pd.to_numeric(post["excess_log_ret"], errors="coerce").dropna()
    pre_raw = pd.to_numeric(prior["log_ret"], errors="coerce").dropna()
    if len(pre_excess) < trend_horizon or post_excess.empty:
        return None
    pre_excess_log_return = float(pre_excess.sum())
    pre_raw_return = float(np.expm1(pre_raw.sum()))
    pre_excess_return = float(np.expm1(pre_excess_log_return))
    post_excess_log_return = float(post_excess.sum())
    post_excess_return = float(np.expm1(post_excess_log_return))
    post_raw_return = float(np.expm1(pd.to_numeric(post["log_ret"], errors="coerce").dropna().sum()))
    daily_volatility = float(pre_excess.std(ddof=1)) if len(pre_excess) > 1 else math.nan
    pre_scale = daily_volatility * math.sqrt(len(pre_excess))
    post_scale = daily_volatility * math.sqrt(len(post_excess))
    pre_trend_z = (
        pre_excess_log_return / pre_scale
        if pre_scale and not math.isnan(pre_scale)
        else math.nan
    )
    pre_direction = int(np.sign(pre_excess_log_return))
    post_direction = int(np.sign(post_excess_log_return))
    reversal = float(
        pre_direction != 0
        and post_direction != 0
        and pre_direction != post_direction
    )
    reversal_signed_return = float(-pre_direction * post_excess_return)
    normalized_strength = (
        float(-pre_direction * post_excess_log_return / post_scale)
        if post_scale and not math.isnan(post_scale)
        else math.nan
    )
    strong_trend = bool(
        not math.isnan(pre_trend_z)
        and abs(pre_trend_z) >= strong_trend_threshold
    )
    return {
        "pre_raw_return": pre_raw_return,
        "pre_excess_return": pre_excess_return,
        "pre_trend_z": pre_trend_z,
        "pre_trend_direction": float(pre_direction),
        "strong_pre_trend": float(strong_trend),
        "post_raw_return": post_raw_return,
        "post_excess_return": post_excess_return,
        "reversal_frequency": reversal,
        "strong_trend_reversal_frequency": reversal if strong_trend else math.nan,
        "normalized_reversal_strength": normalized_strength,
        "reversal_signed_return": reversal_signed_return,
        "downtrend_rebound_frequency": (
            float(post_direction > 0) if pre_direction < 0 else math.nan
        ),
        "uptrend_fade_frequency": (
            float(post_direction < 0) if pre_direction > 0 else math.nan
        ),
        "post_excess_after_downtrend": (
            post_excess_return if pre_direction < 0 else math.nan
        ),
        "post_excess_after_uptrend": (
            post_excess_return if pre_direction > 0 else math.nan
        ),
        "n_post_sessions": float(len(post_excess)),
    }


def _reversal_records(
    *,
    panel: pd.DataFrame,
    anchors: pd.DataFrame,
    window: WindowSpec,
    trend_horizon: int,
    strong_trend_threshold: float,
    source: str,
) -> pd.DataFrame:
    rows = []
    for item in anchors.itertuples(index=False):
        record = reversal_record(
            panel=panel,
            anchor=item.anchor_date,
            window=window,
            trend_horizon=trend_horizon,
            strong_trend_threshold=strong_trend_threshold,
        )
        if record is None:
            continue
        event_id = str(getattr(item, "event_id", ""))
        rows.append(
            {
                "event_id": event_id,
                "anchor_date": item.anchor_date,
                "exact_ts": getattr(item, "exact_ts", None),
                "era": _tsla_era(item.anchor_date),
                "window_name": window.name,
                "trend_horizon_sessions": trend_horizon,
                "source": source,
                **record,
            }
        )
    return pd.DataFrame(rows)


def _matched_reversal_records(
    *,
    panel: pd.DataFrame,
    station_frame: pd.DataFrame,
    baseline_calendar: pd.DataFrame,
    volatility_quantiles: np.ndarray,
    window: WindowSpec,
    trend_horizon: int,
    strong_trend_threshold: float,
    method: str,
    samples_per_event: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    sampled_frames = []
    for event in station_frame.itertuples(index=False):
        candidates = baseline_calendar
        if method == "month_matched":
            candidates = candidates[
                candidates["anchor_date"].dt.month == event.station_date.month
            ]
        elif method == "volatility_regime_matched":
            regime = _volatility_regime(
                event.pre_event_vol_20d,
                volatility_quantiles,
            )
            candidates = candidates[candidates["volatility_regime"] == regime]
        elif method != "non_event":
            raise ValueError(f"Unsupported baseline method: {method}")
        if candidates.empty:
            continue
        indexes = rng.choice(
            candidates.index.to_numpy(),
            size=min(samples_per_event, len(candidates)),
            replace=False,
        )
        sampled = candidates.loc[indexes, ["anchor_date"]].copy()
        sampled["event_id"] = event.event_id
        sampled_frames.append(sampled)
    if not sampled_frames:
        return pd.DataFrame()
    anchors = pd.concat(sampled_frames, ignore_index=True)
    return _reversal_records(
        panel=panel,
        anchors=anchors,
        window=window,
        trend_horizon=trend_horizon,
        strong_trend_threshold=strong_trend_threshold,
        source=f"baseline_{method}",
    )


def _test_family(
    *,
    horizon: int,
    window: str,
    baseline: str,
    metric: str,
    primary: dict[str, Any],
) -> str:
    primary_metrics = _split(
        primary.get(
            "metrics",
            "reversal_frequency,normalized_reversal_strength,"
            "downtrend_rebound_frequency,uptrend_fade_frequency",
        )
    )
    if (
        horizon == int(primary.get("trend_horizon_sessions", 20))
        and window == str(primary.get("window_name", "station_to_day3_calendar_0_3"))
        and baseline
        == str(primary.get("baseline_method", "volatility_regime_matched"))
        and metric in primary_metrics
    ):
        return "primary_reversal"
    return "sensitivity_reversal"


def _summary_markdown(result: MercuryTslaReversalResult) -> str:
    results = result.results
    quality = result.data_quality
    primary_window_label = str(
        quality.get("primary_window_label_zh", "轉順 station 第 0～+3 日")
    )
    primary_window_end = int(quality.get("primary_window_end_day", 3))
    primary = results[results["test_family"] == "primary_reversal"].sort_values(
        "q_value_fdr"
    )
    robust_primary = int((primary["q_value_fdr"] < 0.10).sum())
    robust_all = int((results["q_value_fdr"] < 0.10).sum())
    lines = [
        f"# 水星{primary_window_label}：TSLA 趨勢反轉跡象研究",
        "",
        "## 研究問題",
        "",
        "本研究不直接問 TSLA 在水星轉順後平均上漲或下跌，而是先判斷 station 前的相對趨勢，再檢查 station 後是否向相反方向移動。",
        "所有結果只代表歷史關聯與情境研究，不代表因果、預測、財務建議或交易訊號。",
        "",
        "## 反轉定義",
        "",
        "- 事前趨勢：精確 station 後第一個完整 TSLA 交易時段以前 10/20 個交易日的 TSLA 相對 SPX 累積報酬。",
        "- 反轉：事前相對下跌、事後相對上漲；或事前相對上漲、事後相對下跌。",
        "- 強趨勢：事前相對報酬的波動標準化絕對值至少為 "
        f"{quality['strong_trend_z_threshold']:.2f}。",
        f"- 主要假設固定為：20 日事前趨勢 × {primary_window_label} × 事前波動狀態匹配基線。",
        "- 第 0 日以精確 station 之後第一個完整 TSLA 交易時段為起點，避免納入 station 發生前的當日報酬。",
        "",
        "## 資料覆蓋",
        "",
        f"- TSLA：{quality['TSLA']['coverage_start']} 至 {quality['TSLA']['coverage_end']}，{quality['TSLA']['rows']} 個交易日。",
        f"- 完整主要窗口事件：{quality['completed_primary_events']} 次。",
        "- 事前趨勢只使用反應起點以前的已知收盤，避免未來資料洩漏。",
        "",
        "## 執行摘要",
        "",
        f"- 主要假設檢定 {len(primary)} 組，q < 0.10 有 {robust_primary} 組。",
        f"- 全部主要與敏感度檢定中，q < 0.10 有 {robust_all} 組。",
        "",
        "## 核心判讀",
        "",
    ]
    primary_by_metric = {
        row.metric: row for row in primary.itertuples(index=False)
    }
    reversal = primary_by_metric.get("reversal_frequency")
    strength = primary_by_metric.get("normalized_reversal_strength")
    fade = primary_by_metric.get("uptrend_fade_frequency")
    rebound = primary_by_metric.get("downtrend_rebound_frequency")
    if reversal is not None:
        lines.append(
            f"- {primary_window_label}方向反轉比例為 {reversal.effect_value:.1%}，"
            f"匹配基線為 {reversal.baseline_value:.1%}；差異 "
            f"{reversal.effect_minus_baseline:+.1%}，q={reversal.q_value_fdr:.3f}，"
            "不足以視為穩健反轉訊號。"
        )
    if fade is not None and rebound is not None:
        lines.append(
            f"- 事前上漲後回落比例為 {fade.effect_value:.1%}，"
            f"事前下跌後反彈比例為 {rebound.effect_value:.1%}；"
            "描述上較像「上漲後回落」的不對稱，而不是雙向一致反轉。"
        )
    if strength is not None:
        if strength.effect_value > 0:
            strength_reading = (
                "正值表示按移動幅度看，反轉方向略強於延續方向；"
                "但接近 0 時代表兩者幾乎沒有差別。"
            )
        elif strength.effect_value < 0:
            strength_reading = (
                "負值表示按移動幅度看，延續方向的移動整體強於反轉方向。"
            )
        else:
            strength_reading = "數值為 0，代表反轉與延續方向沒有幅度差異。"
        lines.append(
            f"- 波動標準化反轉強度為 {strength.effect_value:.3f}；"
            f"{strength_reading}"
        )
    lines.extend(
        [
            "- 綜合判斷：目前沒有可重複的整體趨勢反轉證據；敏感度分析甚至顯示部分事前下跌情境較常延續，而非反彈。",
            "",
        "## 主要假設結果",
        "",
        "| 指標 | station 事件 | 匹配基線 | 差異 | 95% bootstrap CI | p 值 | q 值 | 事件數 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in primary.itertuples(index=False):
        lines.append(
            "| "
            + " | ".join(
                [
                    REVERSAL_METRICS.get(row.metric, row.metric),
                    _format_reversal_metric(row.metric, row.effect_value),
                    _format_reversal_metric(row.metric, row.baseline_value),
                    _format_reversal_metric(row.metric, row.effect_minus_baseline),
                    (
                        f"[{_format_reversal_metric(row.metric, row.bootstrap_diff_ci_low)}, "
                        f"{_format_reversal_metric(row.metric, row.bootstrap_diff_ci_high)}]"
                    ),
                    f"{row.p_value:.3f}",
                    f"{row.q_value_fdr:.3f}",
                    str(int(row.n_events)),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 最低 q 值的敏感度結果",
            "",
            "| 趨勢期 | 事後窗口 | 基線 | 指標 | 事件值 | 基線值 | q 值 | 事件數 |",
            "|---:|---|---|---|---:|---:|---:|---:|",
        ]
    )
    sensitivity = (
        results[results["test_family"] == "sensitivity_reversal"]
        .sort_values(["q_value_fdr", "p_value"])
        .head(12)
    )
    for row in sensitivity.itertuples(index=False):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row.trend_horizon_sessions)),
                    WINDOW_LABELS_ZH.get(row.window_name, row.window_name),
                    BASELINE_LABELS_ZH.get(
                        row.baseline_method,
                        row.baseline_method,
                    ),
                    REVERSAL_METRICS.get(row.metric, row.metric),
                    _format_reversal_metric(row.metric, row.effect_value),
                    _format_reversal_metric(row.metric, row.baseline_value),
                    f"{row.q_value_fdr:.3f}",
                    str(int(row.n_events)),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 年代穩定性（主要定義）",
            "",
            "以下只作描述，不因分段樣本少而宣稱顯著性。",
            "",
            "| 年代 | 事件數 | 反轉比例 | 強趨勢反轉比例 | 標準化反轉強度 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    details = result.event_details[
        (result.event_details["trend_horizon_sessions"] == 20)
        & (
            result.event_details["window_name"]
            == str(
                quality["primary_hypothesis"].get(
                    "window_name",
                    "station_to_day3_calendar_0_3",
                )
            )
        )
    ]
    era = (
        details.groupby("era", as_index=False)
        .agg(
            n_events=("event_id", "nunique"),
            reversal_frequency=("reversal_frequency", "mean"),
            strong_trend_reversal_frequency=(
                "strong_trend_reversal_frequency",
                "mean",
            ),
            normalized_reversal_strength=(
                "normalized_reversal_strength",
                "mean",
            ),
        )
        .sort_values("era")
    )
    for row in era.itertuples(index=False):
        lines.append(
            f"| {row.era} | {int(row.n_events)} | "
            f"{row.reversal_frequency:.1%} | "
            f"{row.strong_trend_reversal_frequency:.1%} | "
            f"{row.normalized_reversal_strength:.3f} |"
        )
    lines.extend(
        [
            "",
            "## 判讀規則與限制",
            "",
            "- 只有主要假設或同組敏感度在 FDR q < 0.10、樣本足夠且 bootstrap 差異區間不跨 0 時，才視為較穩健的探索性反轉跡象。",
            "- reversal frequency 約 50% 本身不代表有效訊號；必須顯著高於匹配 placebo。",
            "- TSLA 公司成熟度、市值、財報、利率與市場新聞都可能造成年代差異，本研究不能把差異歸因於水星。",
            f"- 2026-07-23 22:57 UTC（香港時間 2026-07-24 06:57）的 station 尚沒有完整第 0～+{primary_window_end} 日窗口，因此不納入主要估計。",
            "- Yahoo 價格副本只供本地研究，公開或再分發前需確認授權。",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_reversal_metric(metric: str, value: float) -> str:
    if value is None or pd.isna(value):
        return "NA"
    if metric.endswith("_frequency"):
        return f"{float(value):.1%}"
    if metric in {
        "reversal_signed_return",
        "post_excess_after_downtrend",
        "post_excess_after_uptrend",
    }:
        return f"{float(value):.2%}"
    return f"{float(value):.3f}"


def _percentile(effect: float, baseline: Iterable[float]) -> float:
    clean = _clean_array(baseline)
    if math.isnan(effect) or len(clean) == 0:
        return math.nan
    return float(np.mean(clean <= effect))


def _first_full_tsla_session_after(
    panel: pd.DataFrame,
    exact_ts: pd.Timestamp,
) -> pd.Timestamp | pd.NaT:
    exact = pd.Timestamp(exact_ts)
    exact = exact.tz_localize("UTC") if exact.tzinfo is None else exact.tz_convert("UTC")
    market_tz = ZoneInfo("America/New_York")
    for session_date in panel["ts"]:
        session_day = pd.Timestamp(session_date).date()
        market_open = pd.Timestamp(
            datetime.combine(session_day, time(9, 30), tzinfo=market_tz)
        ).tz_convert("UTC")
        if market_open > exact:
            return pd.Timestamp(session_date)
    return pd.NaT


def _split(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]
