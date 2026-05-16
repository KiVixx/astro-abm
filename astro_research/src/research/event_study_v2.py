from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.bootstrap import bootstrap_ci, permutation_p_value
from research.hypotheses import expected_direction_map
from research.io import read_optional_table, read_table
from research.multiple_testing import benjamini_hochberg


RESULT_COLUMNS = [
    "ts",
    "run_id",
    "hypothesis_id",
    "event_family",
    "event_type",
    "asset",
    "window_name",
    "baseline_method",
    "metric",
    "effect_value",
    "baseline_value",
    "effect_minus_baseline",
    "effect_ratio",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "p_value",
    "q_value_fdr",
    "placebo_percentile",
    "expected_direction",
    "effect_direction",
    "effect_direction_match",
    "n_events",
    "n_observations",
    "n_baseline_observations",
    "sample_warning",
    "overlap_warning",
    "coverage_warning",
    "data_version",
    "calc_version",
    "source_note",
    "multiple_testing_group",
]


RUN_COLUMNS = [
    "ts",
    "run_id",
    "hypothesis_id",
    "run_type",
    "event_family",
    "config_hash",
    "git_commit",
    "data_version",
    "astro_dataset_id",
    "start_ts",
    "end_ts",
    "assets",
    "metrics",
    "windows",
    "baseline_methods",
    "status",
    "warning_count",
    "report_path",
    "source_note",
]


@dataclass(frozen=True)
class BatchStudyResult:
    results: pd.DataFrame
    runs: pd.DataFrame
    warnings: list[str]
    run_id: str


def run_research_batch(config_path: str | Path, *, root: str | Path | None = None, run_id_override: str | None = None) -> BatchStudyResult:
    root_path = Path(root or Path.cwd())
    config_text = Path(config_path).read_text()
    raw = _parse_simple_yaml(config_text)
    run_config = raw.get("run", {})
    inputs = raw.get("inputs", {})
    run_id = run_id_override or str(run_config.get("run_id", "research_batch_v1"))
    data_version = str(run_config.get("data_version", "research_batch_v1"))
    calc_version = str(run_config.get("calc_version", "event_study_v2"))
    random_seed = int(run_config.get("random_seed", 42))
    bootstrap_samples = int(run_config.get("bootstrap_samples", 500))
    placebo_samples = int(run_config.get("placebo_samples", 500))

    events = _prepare_events(read_table(_resolve(root_path, str(inputs.get("research_events_path", "")))))
    market = _prepare_market(read_table(_resolve(root_path, str(inputs.get("market_features_path", "")))))
    stress = _prepare_stress(read_optional_table(_resolve(root_path, str(inputs.get("financial_stress_path", "")))))
    hypotheses = read_table(_resolve(root_path, str(inputs.get("hypotheses_path", ""))))
    if "hypothesis_id" not in hypotheses.columns:
        raise ValueError("Formal research batch requires registered hypotheses.")
    rows = []
    run_rows = []
    warnings = []
    placebo_cache: dict[tuple[str, str, str, str], float] = {}
    now = datetime.now(UTC)
    for hypothesis_id, study in raw.get("studies", {}).items():
        hypothesis = hypotheses[hypotheses["hypothesis_id"] == hypothesis_id]
        if hypothesis.empty:
            warnings.append(f"{hypothesis_id}: missing hypothesis registry row.")
            continue
        hypothesis_row = hypothesis.iloc[-1]
        event_family = str(study.get("event_family", hypothesis_row.get("event_family", "")))
        study_events = events[(events["event_family"] == event_family) & (events["eligible_for_event_study"].astype(bool))]
        assets = _split(study.get("assets", hypothesis_row.get("primary_assets", "")))
        metrics = _split(study.get("metrics", hypothesis_row.get("primary_metrics", "")))
        windows = _split(study.get("windows", hypothesis_row.get("windows", "")))
        baselines = _split(study.get("baselines", hypothesis_row.get("baseline_methods", "")))
        direction_map = expected_direction_map(str(hypothesis_row.get("expected_direction", "")))
        warning_count = 0
        for asset in assets:
            asset_market = market[market["asset"] == asset].copy()
            asset_panel = _join_stress(asset_market, stress)
            coverage_warning = "" if not asset_panel.empty else "missing_asset_coverage"
            for window in windows:
                event_window = _expand_events(study_events, window)
                if event_window.empty:
                    continue
                overlap_warning = "overlap_detected" if study_events["is_overlapping"].astype(bool).any() else ""
                for baseline in baselines:
                    baseline_panel = _baseline_panel(asset_panel, event_window, baseline)
                    for metric in metrics:
                        event_values = _metric_values(event_window, asset_panel, metric)
                        baseline_values = _baseline_metric_values(baseline_panel, metric)
                        effect = _mean(event_values)
                        base = _mean(baseline_values)
                        ci_low, ci_high = bootstrap_ci(event_values, samples=bootstrap_samples, seed=random_seed)
                        p_value = permutation_p_value(event_values, baseline_values, samples=bootstrap_samples, seed=random_seed)
                        placebo_key = (event_family, window, asset, metric)
                        if placebo_key not in placebo_cache:
                            placebo_cache[placebo_key] = _placebo_percentile(event_window, asset_panel, metric, effect, samples=placebo_samples, seed=random_seed)
                        placebo = placebo_cache[placebo_key]
                        sample_warning = _sample_warning(
                            n_events=event_window["event_id"].nunique(),
                            n_observations=len(event_values),
                            min_events=int(hypothesis_row.get("min_events", 0)),
                            min_observations=int(hypothesis_row.get("min_observations", 0)),
                        )
                        warning_count += int(bool(sample_warning or overlap_warning or coverage_warning))
                        expected = direction_map.get(metric, "")
                        direction = _effect_direction(effect, base)
                        rows.append(
                            {
                                "ts": now,
                                "run_id": run_id,
                                "hypothesis_id": hypothesis_id,
                                "event_family": event_family,
                                "event_type": event_family,
                                "asset": asset,
                                "window_name": window,
                                "baseline_method": baseline,
                                "metric": metric,
                                "effect_value": effect,
                                "baseline_value": base,
                                "effect_minus_baseline": effect - base if not math.isnan(effect) and not math.isnan(base) else math.nan,
                                "effect_ratio": effect / base if base not in (0, math.nan) and not math.isnan(effect) and not math.isnan(base) else math.nan,
                                "bootstrap_ci_low": ci_low,
                                "bootstrap_ci_high": ci_high,
                                "p_value": p_value,
                                "q_value_fdr": math.nan,
                                "placebo_percentile": placebo,
                                "expected_direction": expected,
                                "effect_direction": direction,
                                "effect_direction_match": _direction_match(expected, direction),
                                "n_events": int(event_window["event_id"].nunique()),
                                "n_observations": int(len(event_values)),
                                "n_baseline_observations": int(len(baseline_values)),
                                "sample_warning": sample_warning,
                                "overlap_warning": overlap_warning,
                                "coverage_warning": coverage_warning,
                                "data_version": data_version,
                                "calc_version": calc_version,
                                "source_note": "association_only;calendar_day",
                                "multiple_testing_group": str(hypothesis_row.get("multiple_testing_group", hypothesis_id)),
                            }
                        )
        run_rows.append(
            {
                "ts": now,
                "run_id": run_id,
                "hypothesis_id": hypothesis_id,
                "run_type": str(run_config.get("run_type", "formal")),
                "event_family": event_family,
                "config_hash": str(hypothesis_row.get("config_hash", "")),
                "git_commit": str(hypothesis_row.get("git_commit", "")),
                "data_version": data_version,
                "astro_dataset_id": "",
                "start_ts": events["event_ts"].min() if not events.empty else pd.NaT,
                "end_ts": events["event_ts"].max() if not events.empty else pd.NaT,
                "assets": ",".join(assets),
                "metrics": ",".join(metrics),
                "windows": ",".join(windows),
                "baseline_methods": ",".join(baselines),
                "status": "completed_with_warnings" if warning_count else "completed",
                "warning_count": warning_count,
                "report_path": "",
                "source_note": "association_only",
            }
        )
    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    if not results.empty:
        results["q_value_fdr"] = np.nan
        for _, group_index in results.groupby("multiple_testing_group").groups.items():
            results.loc[group_index, "q_value_fdr"] = benjamini_hochberg(results.loc[group_index, "p_value"].tolist())
    return BatchStudyResult(results=results, runs=pd.DataFrame(run_rows, columns=RUN_COLUMNS), warnings=warnings, run_id=run_id)


def write_batch_report(batch: BatchStudyResult, output_dir: str | Path, *, config_text: str, hypothesis_snapshot: pd.DataFrame) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary.md": output / "summary.md",
        "results.csv": output / "results.csv",
        "results.parquet": output / "results.parquet",
        "event_study_runs.csv": output / "event_study_runs.csv",
        "event_study_runs.parquet": output / "event_study_runs.parquet",
        "config_snapshot.yaml": output / "config_snapshot.yaml",
        "hypothesis_snapshot.yaml": output / "hypothesis_snapshot.yaml",
        "coverage_report.csv": output / "coverage_report.csv",
        "warnings.json": output / "warnings.json",
    }
    batch.results.to_csv(paths["results.csv"], index=False)
    batch.results.to_parquet(paths["results.parquet"], index=False)
    batch.runs.to_csv(paths["event_study_runs.csv"], index=False)
    batch.runs.to_parquet(paths["event_study_runs.parquet"], index=False)
    paths["config_snapshot.yaml"].write_text(config_text)
    hypothesis_snapshot.to_csv(paths["hypothesis_snapshot.yaml"], index=False)
    _coverage_report(batch.results).to_csv(paths["coverage_report.csv"], index=False)
    paths["warnings.json"].write_text(json.dumps(batch.warnings, indent=2))
    paths["summary.md"].write_text(_summary(batch))
    return paths


def _prepare_events(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["event_ts"] = pd.to_datetime(frame["event_ts"], utc=True).dt.normalize()
    return frame


def _prepare_market(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.normalize()
    return frame


def _prepare_stress(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.normalize()
    return frame


def _join_stress(market: pd.DataFrame, stress: pd.DataFrame) -> pd.DataFrame:
    if market.empty:
        return market
    if stress.empty:
        return market
    return market.merge(stress, on="ts", how="left", suffixes=("", "_stress"))


def _expand_events(events: pd.DataFrame, window: str) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    if window == "event_days":
        days = (0, 0)
    elif window.startswith("pm"):
        size = int(window.removeprefix("pm"))
        days = (-size, size)
    else:
        return pd.DataFrame()
    rows = []
    for event in events.itertuples(index=False):
        for rel_day in range(days[0], days[1] + 1):
            rows.append({"ts": event.event_ts + timedelta(days=rel_day), "event_id": event.event_id, "rel_day": rel_day})
    return pd.DataFrame(rows)


def _baseline_panel(panel: pd.DataFrame, event_window: pd.DataFrame, method: str) -> pd.DataFrame:
    if panel.empty:
        return panel
    baseline = panel[~panel["ts"].isin(set(event_window["ts"]))].copy()
    if method == "month_matched":
        baseline = baseline[baseline["ts"].dt.month.isin(set(event_window["ts"].dt.month))]
    elif method == "weekday_matched":
        baseline = baseline[baseline["ts"].dt.weekday.isin(set(event_window["ts"].dt.weekday))]
    elif method == "volatility_regime_matched" and "realized_vol_20d" in baseline.columns:
        threshold = pd.to_numeric(panel["realized_vol_20d"], errors="coerce").median()
        event_median = pd.to_numeric(panel[panel["ts"].isin(set(event_window["ts"]))]["realized_vol_20d"], errors="coerce").median()
        baseline = baseline[(baseline["realized_vol_20d"] >= threshold) == (event_median >= threshold)]
    return baseline


def _metric_values(event_window: pd.DataFrame, panel: pd.DataFrame, metric: str) -> list[float]:
    panel = panel.drop(columns=["event_id", "rel_day"], errors="ignore")
    joined = event_window.merge(panel, on="ts", how="inner")
    if joined.empty:
        return []
    if metric in {"mean_log_ret", "median_log_ret", "cumulative_log_ret"}:
        source = "log_ret_1d"
    elif metric == "realized_vol":
        source = "realized_vol_20d"
    elif metric == "max_drawdown":
        source = "drawdown_20d"
    elif metric == "extreme_absret_frequency":
        source = "is_extreme_absret_95"
    elif metric in {"cross_asset_stress_score", "stress_score_mean"}:
        source = "cross_asset_stress_score"
    elif metric == "vix_spike_frequency":
        source = "is_vol_stress"
    elif metric == "vol_stress_score":
        source = "vol_stress_score"
    elif metric == "credit_stress_score":
        source = "credit_stress_score"
    else:
        source = metric
    values = []
    for _, group in joined.groupby("event_id"):
        series = pd.to_numeric(group[source], errors="coerce") if source in group.columns else pd.Series(dtype=float)
        if source.startswith("is_"):
            series = group[source].astype("boolean").astype(float)
        if series.dropna().empty:
            continue
        if metric == "cumulative_log_ret":
            values.append(float(series.sum()))
        elif metric == "median_log_ret":
            values.append(float(series.median()))
        elif metric in {"extreme_absret_frequency", "vix_spike_frequency"}:
            values.append(float(series.mean()))
        else:
            values.append(float(series.mean()))
    return values


def _baseline_metric_values(panel: pd.DataFrame, metric: str) -> list[float]:
    if panel.empty:
        return []
    pseudo = panel.copy()
    pseudo["event_id"] = "baseline"
    return _metric_values(pseudo[["ts", "event_id"]], pseudo, metric)


def _placebo_percentile(event_window: pd.DataFrame, panel: pd.DataFrame, metric: str, effect: float, *, samples: int, seed: int) -> float:
    if math.isnan(effect) or event_window.empty or panel.empty:
        return math.nan
    eligible = panel[~panel["ts"].isin(set(event_window["ts"]))]["ts"].drop_duplicates().to_numpy()
    if len(eligible) == 0:
        return math.nan
    rel_days = sorted(event_window["rel_day"].drop_duplicates().astype(int).tolist())
    event_count = event_window["event_id"].nunique()
    rng = np.random.default_rng(seed)
    effects = []
    for _ in range(samples):
        dates = rng.choice(eligible, size=event_count, replace=len(eligible) < event_count)
        rows = []
        for index, date_value in enumerate(pd.to_datetime(dates, utc=True)):
            for rel_day in rel_days:
                rows.append({"ts": date_value.normalize() + timedelta(days=rel_day), "event_id": f"placebo_{index}", "rel_day": rel_day})
        effects.append(_mean(_metric_values(pd.DataFrame(rows), panel, metric)))
    clean = np.asarray([value for value in effects if not math.isnan(value)])
    return float(np.mean(clean <= effect)) if len(clean) else math.nan


def _sample_warning(*, n_events: int, n_observations: int, min_events: int, min_observations: int) -> str:
    if n_events < min_events:
        return "insufficient_events"
    if n_observations < min_observations:
        return "insufficient_observations"
    return ""


def _effect_direction(effect: float, baseline: float) -> str:
    if math.isnan(effect) or math.isnan(baseline):
        return ""
    if effect > baseline:
        return "higher"
    if effect < baseline:
        return "lower"
    return "flat"


def _direction_match(expected: str, actual: str) -> bool | None:
    if not expected:
        return None
    return expected == actual


def _mean(values) -> float:
    array = np.asarray(values, dtype=float)
    array = array[~np.isnan(array)]
    return float(array.mean()) if len(array) else math.nan


def _coverage_report(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame(columns=["asset", "coverage_warning_count"])
    return results.groupby("asset", as_index=False)["coverage_warning"].apply(lambda series: int(series.astype(bool).sum())).rename(columns={"coverage_warning": "coverage_warning_count"})


def _summary(batch: BatchStudyResult) -> str:
    run_type = str(batch.runs["run_type"].iloc[0]) if not batch.runs.empty and "run_type" in batch.runs.columns else ""
    not_formal = run_type == "real_data_smoke"
    if batch.results.empty:
        findings = "No rows produced.\n"
    else:
        grouped = batch.results.groupby("hypothesis_id").agg(rows=("metric", "count"), min_q=("q_value_fdr", "min"), warnings=("sample_warning", lambda s: int(s.astype(bool).sum()))).reset_index()
        lines = ["| hypothesis | rows | min_q | warning_rows | status |", "|---|---:|---:|---:|---|"]
        for row in grouped.itertuples(index=False):
            status = "insufficient_sample" if row.warnings else ("suggestive" if row.min_q < 0.10 else "exploratory")
            lines.append(f"| {row.hypothesis_id} | {row.rows} | {row.min_q:.4g} | {row.warnings} | {status} |")
        findings = "\n".join(lines) + "\n"
    return (
        "# Research Batch Summary\n\n"
        f"run_id: `{batch.run_id}`\n\n"
        f"run_type: `{run_type}`\n\n"
        f"not_formal_research: `{str(not_formal).lower()}`\n\n"
        "Interpretation: historical association only; no causal claim is made. "
        + ("This smoke run is for data and pipeline validation, not a formal research conclusion.\n\n" if not_formal else "\n\n")
        + "## Primary Results\n\n"
        + f"{findings}\n"
        + "## Warnings\n\n"
        + ("\n".join(f"- {warning}" for warning in batch.warnings) if batch.warnings else "- none")
        + "\n"
    )


def _split(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
