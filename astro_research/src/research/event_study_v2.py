from __future__ import annotations

import json
import math
import re
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
    "n_events_with_asset_coverage",
    "n_events_total",
    "coverage_pct",
    "n_observations",
    "n_baseline_observations",
    "asset_start",
    "asset_end",
    "missing_components",
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
    placebo_event_cap = int(run_config.get("placebo_event_cap", 0))
    run_metadata = _run_metadata(run_config, raw.get("asset_groups", {}))

    events = _prepare_events(read_table(_resolve(root_path, str(inputs.get("research_events_path", "")))))
    market = _prepare_market(read_table(_resolve(root_path, str(inputs.get("market_features_path", "")))))
    stress = _prepare_stress(read_optional_table(_resolve(root_path, str(inputs.get("financial_stress_path", "")))))
    hypotheses = read_table(_resolve(root_path, str(inputs.get("hypotheses_path", ""))))
    if "hypothesis_id" not in hypotheses.columns:
        raise ValueError("Formal research batch requires registered hypotheses.")
    rows = []
    run_rows = []
    warnings = _metadata_warnings(run_metadata)
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
            if asset_panel.empty and asset in {"CreditProxy", "HY_OAS"} and not stress.empty:
                asset_panel = _stress_only_panel(stress, asset=asset)
            coverage_warning = "" if not asset_panel.empty else "missing_asset_coverage"
            asset_start = asset_panel["ts"].min() if not asset_panel.empty and "ts" in asset_panel.columns else pd.NaT
            asset_end = asset_panel["ts"].max() if not asset_panel.empty and "ts" in asset_panel.columns else pd.NaT
            for window in windows:
                event_window = _expand_events(study_events, window)
                if event_window.empty:
                    continue
                coverage = _event_coverage(event_window, asset_panel, total_events=int(study_events["event_id"].nunique()))
                missing_components = _missing_components(asset, asset_panel, metrics)
                overlap_warning = "overlap_detected" if study_events["is_overlapping"].astype(bool).any() else ""
                for baseline in baselines:
                    baseline_warning = "weekday_matched_unstable_for_sparse_history" if baseline == "weekday_matched" and coverage["n_events_with_asset_coverage"] < 20 else ""
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
                            placebo_cache[placebo_key] = _placebo_percentile(event_window, asset_panel, metric, effect, samples=placebo_samples, seed=random_seed, event_cap=placebo_event_cap)
                        placebo = placebo_cache[placebo_key]
                        sample_warning = _sample_warning(
                            n_events=coverage["n_events_with_asset_coverage"],
                            n_observations=len(event_values),
                            min_events=int(hypothesis_row.get("min_events", 0)),
                            min_observations=int(hypothesis_row.get("min_observations", 0)),
                        )
                        combined_coverage_warning = ";".join(item for item in (coverage_warning, baseline_warning) if item)
                        warning_count += int(bool(sample_warning or overlap_warning or combined_coverage_warning or missing_components))
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
                                "n_events_with_asset_coverage": coverage["n_events_with_asset_coverage"],
                                "n_events_total": coverage["n_events_total"],
                                "coverage_pct": coverage["coverage_pct"],
                                "n_observations": int(len(event_values)),
                                "n_baseline_observations": int(len(baseline_values)),
                                "asset_start": asset_start,
                                "asset_end": asset_end,
                                "missing_components": ",".join(missing_components),
                                "sample_warning": sample_warning,
                                "overlap_warning": overlap_warning,
                                "coverage_warning": combined_coverage_warning,
                                "data_version": data_version,
                                "calc_version": calc_version,
                                "source_note": _source_note(run_metadata),
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
                "source_note": _source_note(run_metadata),
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
        "top_findings.md": output / "top_findings.md",
    }
    batch.results.to_csv(paths["results.csv"], index=False)
    batch.results.to_parquet(paths["results.parquet"], index=False)
    batch.runs.to_csv(paths["event_study_runs.csv"], index=False)
    batch.runs.to_parquet(paths["event_study_runs.parquet"], index=False)
    paths["config_snapshot.yaml"].write_text(config_text)
    hypothesis_snapshot.to_csv(paths["hypothesis_snapshot.yaml"], index=False)
    _coverage_report(batch.results).to_csv(paths["coverage_report.csv"], index=False)
    paths["warnings.json"].write_text(json.dumps(_warnings_payload(batch), indent=2))
    paths["summary.md"].write_text(_summary(batch))
    paths["top_findings.md"].write_text(top_findings_markdown(batch.results))
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


def _stress_only_panel(stress: pd.DataFrame, *, asset: str) -> pd.DataFrame:
    panel = stress.copy()
    panel["asset"] = asset
    panel["source"] = "financial_stress_daily"
    panel["log_ret_1d"] = math.nan
    panel["realized_vol_20d"] = math.nan
    panel["drawdown_20d"] = math.nan
    panel["is_extreme_absret_95"] = math.nan
    return panel


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
    elif metric == "cross_asset_stress_frequency":
        source = "is_cross_asset_stress"
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
        elif metric in {"extreme_absret_frequency", "vix_spike_frequency", "cross_asset_stress_frequency"}:
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


def _placebo_percentile(event_window: pd.DataFrame, panel: pd.DataFrame, metric: str, effect: float, *, samples: int, seed: int, event_cap: int = 0) -> float:
    if math.isnan(effect) or event_window.empty or panel.empty:
        return math.nan
    if event_cap and event_window["event_id"].nunique() > event_cap:
        rng = np.random.default_rng(seed)
        sampled_ids = rng.choice(event_window["event_id"].drop_duplicates().to_numpy(), size=event_cap, replace=False)
        event_window = event_window[event_window["event_id"].isin(set(sampled_ids))].copy()
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
        return pd.DataFrame(columns=["hypothesis_id", "asset", "asset_start", "asset_end", "n_events_with_asset_coverage", "n_events_total", "coverage_pct", "missing_components", "coverage_warning_count"])
    return (
        results.groupby(["hypothesis_id", "asset"], as_index=False)
        .agg(
            asset_start=("asset_start", "min"),
            asset_end=("asset_end", "max"),
            n_events_with_asset_coverage=("n_events_with_asset_coverage", "max"),
            n_events_total=("n_events_total", "max"),
            coverage_pct=("coverage_pct", "max"),
            missing_components=("missing_components", _join_unique),
            coverage_warning_count=("coverage_warning", lambda series: int(series.astype(bool).sum())),
        )
    )


def _summary(batch: BatchStudyResult) -> str:
    run_type = str(batch.runs["run_type"].iloc[0]) if not batch.runs.empty and "run_type" in batch.runs.columns else ""
    not_formal = run_type == "real_data_smoke"
    exploratory = run_type == "exploratory_formal_batch"
    if batch.results.empty:
        grouped = pd.DataFrame(columns=["hypothesis_id", "rows", "min_q", "warnings", "coverage"])
    else:
        grouped = batch.results.groupby("hypothesis_id").agg(
            rows=("metric", "count"),
            min_q=("q_value_fdr", "min"),
            warnings=("sample_warning", lambda s: int(s.astype(bool).sum())),
            coverage=("coverage_pct", "mean"),
        ).reset_index()
    run_hypotheses = batch.runs[["hypothesis_id"]].drop_duplicates() if not batch.runs.empty else pd.DataFrame(columns=["hypothesis_id"])
    grouped = run_hypotheses.merge(grouped, on="hypothesis_id", how="left")
    lines = ["| hypothesis | rows | min_q | mean coverage | warning_rows | status |", "|---|---:|---:|---:|---:|---|"]
    for row in grouped.itertuples(index=False):
        rows = int(row.rows) if pd.notna(row.rows) else 0
        warnings = int(row.warnings) if pd.notna(row.warnings) else 0
        min_q = float(row.min_q) if pd.notna(row.min_q) else math.nan
        coverage = float(row.coverage) if pd.notna(row.coverage) else 0.0
        status = "no_eligible_rows" if rows == 0 else ("insufficient_sample" if warnings else ("suggestive" if min_q < 0.10 else "exploratory"))
        min_q_text = f"{min_q:.4g}" if not math.isnan(min_q) else "nan"
        lines.append(f"| {row.hypothesis_id} | {rows} | {min_q_text} | {coverage:.2%} | {warnings} | {status} |")
    findings = "\n".join(lines) + "\n"
    warning_payload = _warnings_payload(batch)
    return (
        "# Exploratory Formal Batch Summary\n\n"
        "## Executive Summary\n\n"
        f"run_id: `{batch.run_id}`\n\n"
        f"run_type: `{run_type}`\n\n"
        f"not_publication_grade: `{str(exploratory).lower()}`\n\n"
        "This run is exploratory and association-only. It is not publication-grade.\n\n"
        "## Data Readiness Status\n\n"
        "Formal readiness gate allowed exploratory formal batch execution with warnings.\n\n"
        "## Major Caveats\n\n"
        "- Local data provenance is incomplete.\n"
        "- Results are coverage-aware and should be reviewed by asset history.\n"
        "- This report is for hypothesis review, not operational decisions.\n\n"
        "## Source/Licensing Warnings\n\n"
        "- Yahoo-derived local SPX/DXY data is local research only and needs licensing review.\n"
        "- LBMA/ICE gold data needs licensing review before publication.\n\n"
        "## Credit Proxy Warning\n\n"
        "- CreditProxy uses BAA_MINUS_AAA and is not equivalent to ICE/BofA HY OAS.\n\n"
        "## Hypothesis-by-Hypothesis Results\n\n"
        + f"{findings}\n"
        + "## Robustness Checks\n\n"
        "Baselines include non_event, month_matched, and volatility_regime_matched where configured. Weekday matching may be unstable for sparse early-history windows. Large event-family placebo calculations may use the configured event cap for maintainable exploratory runtime.\n\n"
        "## Placebo Summary\n\n"
        + _placebo_summary(batch.results)
        + "\n## FDR Summary\n\n"
        + _fdr_summary(batch.results)
        + "\n## Warnings\n\n"
        + ("\n".join(f"- {item['category']}: {item['message']}" for item in warning_payload["warnings"]) if warning_payload["warnings"] else "- none")
        + "\n\n## Interpretation\n\n"
        "Association only, not causal. No operational recommendation is made.\n\n"
        "## Recommended Next Studies\n\n"
        "- Re-run after provenance fields are completed.\n"
        "- Replace credit proxy with licensed long-history HY OAS if available.\n"
        "- Compare results against randomized astro-event placebo calendars.\n"
    )


def _split(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _event_coverage(event_window: pd.DataFrame, panel: pd.DataFrame, *, total_events: int) -> dict[str, Any]:
    if event_window.empty or panel.empty:
        return {"n_events_with_asset_coverage": 0, "n_events_total": total_events, "coverage_pct": 0.0}
    observed_dates = set(panel["ts"].dropna())
    covered = event_window[event_window["ts"].isin(observed_dates)]["event_id"].nunique()
    return {
        "n_events_with_asset_coverage": int(covered),
        "n_events_total": int(total_events),
        "coverage_pct": float(covered / total_events) if total_events else 0.0,
    }


def _missing_components(asset: str, panel: pd.DataFrame, metrics: list[str]) -> list[str]:
    missing = []
    required = {
        "cumulative_log_ret": "log_ret_1d",
        "realized_vol": "realized_vol_20d",
        "max_drawdown": "drawdown_20d",
        "extreme_absret_frequency": "is_extreme_absret_95",
        "stress_score_mean": "cross_asset_stress_score",
        "cross_asset_stress_frequency": "is_cross_asset_stress",
        "vol_stress_score": "vol_stress_score",
        "credit_stress_score": "credit_stress_score",
    }
    for metric in metrics:
        column = required.get(metric, metric)
        if panel.empty or column not in panel.columns or pd.to_numeric(panel[column], errors="coerce").dropna().empty:
            missing.append(column)
    if asset in {"CreditProxy", "HY_OAS"}:
        return [item for item in missing if item not in {"log_ret_1d", "realized_vol_20d", "drawdown_20d", "is_extreme_absret_95"}]
    return sorted(set(missing))


def _run_metadata(run_config: dict[str, Any], asset_groups: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "run_type",
        "not_publication_grade",
        "association_only",
        "local_data_warnings",
        "credit_proxy_used",
        "yahoo_source_used",
        "lbma_source_used",
    )
    metadata = {key: run_config.get(key) for key in keys if key in run_config}
    metadata["long_history_assets"] = str(asset_groups.get("long_history_assets", ""))
    metadata["modern_assets"] = str(asset_groups.get("modern_assets", ""))
    return metadata


def _metadata_warnings(metadata: dict[str, Any]) -> list[str]:
    warnings = []
    if metadata.get("yahoo_source_used"):
        warnings.append("licensing: Yahoo local data is local research only; redistribution_allowed=false; publication_grade=false.")
    if metadata.get("lbma_source_used"):
        warnings.append("licensing: LBMA/ICE gold data requires licensing review before publication.")
    if metadata.get("credit_proxy_used"):
        warnings.append(f"credit_proxy: {metadata['credit_proxy_used']} is not equivalent to ICE/BofA HY OAS.")
    if metadata.get("not_publication_grade"):
        warnings.append("readiness: exploratory run is not publication-grade.")
    return warnings


def _source_note(metadata: dict[str, Any]) -> str:
    parts = [
        "association_only",
        f"run_type={metadata.get('run_type', '')}",
        f"not_publication_grade={metadata.get('not_publication_grade', '')}",
        f"credit_proxy_used={metadata.get('credit_proxy_used', '')}",
        f"yahoo_source_used={metadata.get('yahoo_source_used', '')}",
        f"lbma_source_used={metadata.get('lbma_source_used', '')}",
    ]
    return ";".join(parts)


def top_findings_markdown(results: pd.DataFrame, *, q_threshold: float = 0.10) -> str:
    lines = [
        "# Top Findings",
        "",
        "Threshold: `q_value_fdr < 0.10` with no sample warning and non-zero covered events.",
        "",
        "Interpretation: association only, not causal. No operational recommendation is made.",
        "",
    ]
    if results.empty:
        return "\n".join(lines + ["No robust findings under current thresholds.\n"])
    eligible = results[
        (pd.to_numeric(results["q_value_fdr"], errors="coerce") < q_threshold)
        & (results["sample_warning"].fillna("") == "")
        & (pd.to_numeric(results["n_events_with_asset_coverage"], errors="coerce") > 0)
    ].copy()
    if eligible.empty:
        return "\n".join(lines + ["No robust findings under current thresholds.\n"])
    eligible = eligible.sort_values(["q_value_fdr", "hypothesis_id", "asset"]).head(25)
    lines.extend(["| hypothesis | asset | window | baseline | metric | q_value_fdr | effect_minus_baseline | caveat |", "|---|---|---|---|---|---:|---:|---|"])
    for row in eligible.itertuples(index=False):
        caveat = "Exploratory local-data result; review coverage, licensing, proxy, and placebo robustness."
        lines.append(
            f"| {row.hypothesis_id} | {row.asset} | {row.window_name} | {row.baseline_method} | {row.metric} | "
            f"{row.q_value_fdr:.4g} | {row.effect_minus_baseline:.4g} | {caveat} |"
        )
    return "\n".join(lines) + "\n"


def validate_exploratory_batch_outputs(output_dir: str | Path) -> list[str]:
    output = Path(output_dir)
    warnings: list[str] = []
    forbidden = ("caused", "causes", "predicts with certainty", "guaranteed", "trading signal")
    for name in ("summary.md", "top_findings.md"):
        path = output / name
        if not path.exists():
            warnings.append(f"{name}: missing")
            continue
        text = path.read_text().lower()
        for phrase in forbidden:
            if phrase in text:
                warnings.append(f"{name}: forbidden causal/operational phrase `{phrase}`")
    runs_path = output / "event_study_runs.csv"
    if runs_path.exists():
        runs = pd.read_csv(runs_path)
        if "run_type" in runs.columns and (runs["run_type"] == "final").any():
            warnings.append("run_type must not be final")
    else:
        warnings.append("event_study_runs.csv: missing")
    warnings_path = output / "warnings.json"
    if warnings_path.exists():
        payload = json.loads(warnings_path.read_text())
        text = json.dumps(payload).lower()
        if "licensing" not in text:
            warnings.append("warnings.json missing licensing caveat")
        if "credit_proxy" not in text and "baa_minus_aaa" not in text:
            warnings.append("warnings.json missing credit proxy caveat")
    else:
        warnings.append("warnings.json: missing")
    results_path = output / "results.parquet"
    if results_path.exists():
        results = pd.read_parquet(results_path)
        if "hypothesis_id" not in results.columns or results["hypothesis_id"].isna().any() or (results["hypothesis_id"].astype(str) == "").any():
            warnings.append("all formal results must reference hypothesis_id")
    elif (output / "results.csv").exists():
        results = pd.read_csv(output / "results.csv")
        if "hypothesis_id" not in results.columns or results["hypothesis_id"].isna().any() or (results["hypothesis_id"].astype(str) == "").any():
            warnings.append("all formal results must reference hypothesis_id")
    else:
        warnings.append("results file missing")
    return warnings


def _warnings_payload(batch: BatchStudyResult) -> dict[str, Any]:
    warnings = []
    for warning in batch.warnings:
        if ":" in warning:
            category, message = warning.split(":", 1)
            warnings.append({"category": category.strip(), "message": message.strip()})
        else:
            warnings.append({"category": "batch", "message": warning})
    return {"warnings": warnings, "warning_count": len(warnings)}


def _placebo_summary(results: pd.DataFrame) -> str:
    if results.empty or "placebo_percentile" not in results.columns:
        return "- no placebo results\n"
    clean = pd.to_numeric(results["placebo_percentile"], errors="coerce").dropna()
    if clean.empty:
        return "- no valid placebo percentiles\n"
    return f"- median placebo percentile: {clean.median():.4f}\n- rows with placebo percentile: {len(clean)}\n"


def _fdr_summary(results: pd.DataFrame) -> str:
    if results.empty or "q_value_fdr" not in results.columns:
        return "- no FDR results\n"
    q = pd.to_numeric(results["q_value_fdr"], errors="coerce")
    return f"- rows q<0.10: {int((q < 0.10).sum())}\n- minimum q: {q.min():.4g}\n"


def _join_unique(values: pd.Series) -> str:
    tokens = []
    for value in values.dropna().astype(str):
        tokens.extend(item for item in value.split(",") if item)
    return ",".join(sorted(set(tokens)))


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
