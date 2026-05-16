from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.io import read_optional_table


REQUIRED_PROVENANCE_FIELDS = (
    "source",
    "original_symbol_or_series",
    "retrieval_method",
    "retrieved_at",
    "coverage_start",
    "coverage_end",
    "original_frequency",
    "transformed_frequency",
    "fill_method",
    "license_note",
    "redistribution_allowed",
    "publication_grade",
    "caveats",
)

DEFAULT_CRISIS_EVENTS = (
    ("1929_crash", "1929 Crash", "1929-10-24"),
    ("1973_oil_crisis", "1973 Oil Crisis", "1973-10-17"),
    ("1987_black_monday", "1987 Black Monday", "1987-10-19"),
    ("2000_dotcom_crash", "2000 Dot-com Crash", "2000-03-10"),
    ("2008_gfc", "2008 Global Financial Crisis", "2008-09-15"),
    ("2020_covid_crash", "2020 COVID Crash", "2020-03-16"),
    ("2022_rate_shock", "2022 Rate Shock", "2022-06-13"),
)


@dataclass(frozen=True)
class ReadinessResult:
    status: str
    warnings: tuple[dict[str, str], ...]
    warning_counts: dict[str, int]
    provenance: list[dict[str, Any]]
    data_quality: dict[str, Any]
    crisis_summaries: list[dict[str, Any]]
    stress_sanity: list[dict[str, Any]]
    metrics: dict[str, Any]
    can_run_exploratory_formal_batch: bool


def build_formal_readiness(
    *,
    root: str | Path,
    market_features_path: str | Path,
    market_bars_path: str | Path,
    macro_observations_path: str | Path,
    financial_stress_path: str | Path,
    provenance_path: str | Path,
    market_config_path: str | Path,
    macro_config_path: str | Path,
    output_markdown_path: str | Path,
    output_json_path: str | Path,
    extreme_return_threshold: float = 0.20,
    long_flat_run_days: int = 10,
) -> ReadinessResult:
    root_path = Path(root)
    market = read_optional_table(_resolve(root_path, market_features_path))
    bars = read_optional_table(_resolve(root_path, market_bars_path))
    macro = read_optional_table(_resolve(root_path, macro_observations_path))
    stress = read_optional_table(_resolve(root_path, financial_stress_path))
    provenance_file = _resolve(root_path, provenance_path)
    provenance = _load_provenance(provenance_file)
    warnings: list[dict[str, str]] = []

    _check_provenance(provenance=provenance, path=provenance_file, warnings=warnings)
    quality = run_data_quality_checks(
        bars=bars,
        macro=macro,
        provenance=provenance,
        market_config_path=_resolve(root_path, market_config_path),
        macro_config_path=_resolve(root_path, macro_config_path),
        warnings=warnings,
        extreme_return_threshold=extreme_return_threshold,
        long_flat_run_days=long_flat_run_days,
    )
    crisis_summaries = build_crisis_sanity_summaries(market_features=market, market_bars=bars, macro=macro, stress=stress)
    stress_sanity = run_stress_sanity_checks(stress=stress, warnings=warnings)
    metrics = _readiness_metrics(market=market, stress=stress, provenance=provenance)
    status = readiness_status(metrics=metrics, warnings=warnings)
    result = ReadinessResult(
        status=status,
        warnings=tuple(warnings),
        warning_counts=dict(Counter(warning["category"] for warning in warnings)),
        provenance=provenance,
        data_quality=quality,
        crisis_summaries=crisis_summaries,
        stress_sanity=stress_sanity,
        metrics=metrics,
        can_run_exploratory_formal_batch=status in {"ready_for_exploratory_formal_batch", "ready_with_warnings"},
    )
    write_readiness_outputs(result, markdown_path=_resolve(root_path, output_markdown_path), json_path=_resolve(root_path, output_json_path))
    return result


def run_data_quality_checks(
    *,
    bars: pd.DataFrame,
    macro: pd.DataFrame,
    provenance: list[dict[str, Any]],
    market_config_path: Path,
    macro_config_path: Path,
    warnings: list[dict[str, str]],
    extreme_return_threshold: float,
    long_flat_run_days: int,
) -> dict[str, Any]:
    quality: dict[str, Any] = {"series": {}}
    if bars.empty:
        _warn(warnings, "data_quality", "market_daily_bars missing_or_empty")
        return quality
    working = bars.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    for asset in ("SPX", "Gold", "DXY"):
        group = working[working.get("asset") == asset].copy()
        summary = _price_quality_summary(group, asset=asset, threshold=extreme_return_threshold, long_flat_run_days=long_flat_run_days)
        quality["series"][asset] = summary
        if summary["duplicate_dates"]:
            _warn(warnings, "data_quality", f"{asset}: duplicate_dates={summary['duplicate_dates']}")
        if summary["missing_close"]:
            _warn(warnings, "data_quality", f"{asset}: missing_close={summary['missing_close']}")
        if summary["non_positive_prices"]:
            _warn(warnings, "data_quality", f"{asset}: non_positive_prices={summary['non_positive_prices']}")
        if summary["extreme_return_count"]:
            _warn(warnings, "data_quality", f"{asset}: extreme_one_day_returns>{extreme_return_threshold:.2%} count={summary['extreme_return_count']}")
        if summary["long_flat_run_count"]:
            _warn(warnings, "data_quality", f"{asset}: long_flat_runs>={long_flat_run_days}d count={summary['long_flat_run_count']}")
        if summary["timezone_normalized"] is False:
            _warn(warnings, "data_quality", f"{asset}: timezone_not_utc_normalized")
    if macro.empty:
        _warn(warnings, "data_quality", "macro_daily_observations missing_or_empty")
    else:
        proxy = macro[macro.get("series_id") == "BAMLH0A0HYM2"].copy()
        if not proxy.empty and set(proxy.get("source", pd.Series(dtype=str)).dropna().unique()) == {"local_csv"}:
            _warn(warnings, "credit_proxy", "BAMLH0A0HYM2 is sourced from local credit proxy; not true ICE/BofA HY OAS.")
    _check_local_source_provenance_configs(market_config_path=market_config_path, macro_config_path=macro_config_path, provenance=provenance, warnings=warnings)
    return quality


def build_crisis_sanity_summaries(*, market_features: pd.DataFrame, market_bars: pd.DataFrame, macro: pd.DataFrame, stress: pd.DataFrame) -> list[dict[str, Any]]:
    market_features = _prepare_ts(market_features)
    market_bars = _prepare_ts(market_bars)
    macro = _prepare_ts(macro)
    stress = _prepare_ts(stress)
    summaries = []
    for event_id, event_name, event_date in DEFAULT_CRISIS_EVENTS:
        center = pd.Timestamp(event_date, tz="UTC")
        left = center - pd.Timedelta(days=90)
        right = center + pd.Timedelta(days=90)
        feature_window = market_features[(market_features["ts"] >= left) & (market_features["ts"] <= right)] if not market_features.empty else pd.DataFrame()
        bar_window = market_bars[(market_bars["ts"] >= left) & (market_bars["ts"] <= right)] if not market_bars.empty else pd.DataFrame()
        macro_window = macro[(macro["ts"] >= left) & (macro["ts"] <= right)] if not macro.empty else pd.DataFrame()
        stress_window = stress[(stress["ts"] >= left) & (stress["ts"] <= right)] if not stress.empty else pd.DataFrame()
        missing = []
        spx_drawdown = _asset_window_drawdown(feature_window, "SPX")
        if math.isnan(spx_drawdown):
            missing.append("SPX")
        summary = {
            "event_id": event_id,
            "event_name": event_name,
            "event_date": event_date,
            "spx_max_drawdown": spx_drawdown,
            "vix_max": _macro_window_max(macro_window, "VIXCLS", missing, "VIX"),
            "dxy_move": _asset_window_move(bar_window, "DXY", missing),
            "gold_move": _asset_window_move(bar_window, "Gold", missing),
            "credit_proxy_change": _macro_window_change(macro_window, "BAMLH0A0HYM2", missing, "credit_proxy"),
            "cross_asset_stress_score_max": _stress_window_max(stress_window, missing),
            "missing_component_list": sorted(set(missing)),
        }
        summaries.append(summary)
    return summaries


def run_stress_sanity_checks(*, stress: pd.DataFrame, warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    prepared = _prepare_ts(stress)
    checks = []
    for event_id, label, date_text in (("2008_gfc", "2008 financial stress", "2008-09-15"), ("2020_covid_crash", "2020 COVID stress", "2020-03-16")):
        center = pd.Timestamp(date_text, tz="UTC")
        window = prepared[(prepared["ts"] >= center - pd.Timedelta(days=30)) & (prepared["ts"] <= center + pd.Timedelta(days=30))] if not prepared.empty else pd.DataFrame()
        max_score = float(window["cross_asset_stress_score"].max()) if not window.empty and "cross_asset_stress_score" in window else float("nan")
        elevated = bool(pd.notna(max_score) and max_score >= 0.5)
        checks.append({"event_id": event_id, "label": label, "max_cross_asset_stress_score": max_score, "elevated": elevated})
        if not elevated:
            _warn(warnings, "stress_sanity", f"{label} not elevated in +/-30d window")
    return checks


def readiness_status(*, metrics: dict[str, Any], warnings: list[dict[str, str]]) -> str:
    if not metrics.get("has_spx_long_history", False):
        return "not_ready"
    if not metrics.get("has_financial_stress_daily", False):
        return "not_ready"
    if not metrics.get("has_local_provenance", False):
        return "not_ready"
    if metrics.get("cross_asset_non_null_ratio", 0.0) < 0.50:
        return "not_ready"
    warning_categories = {warning["category"] for warning in warnings}
    if warning_categories:
        return "ready_with_warnings"
    return "ready_for_exploratory_formal_batch"


def write_readiness_outputs(result: ReadinessResult, *, markdown_path: Path, json_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": result.status,
        "can_run_exploratory_formal_batch": result.can_run_exploratory_formal_batch,
        "warning_counts": result.warning_counts,
        "warnings": list(result.warnings),
        "metrics": result.metrics,
        "data_quality": result.data_quality,
        "crisis_summaries": result.crisis_summaries,
        "stress_sanity": result.stress_sanity,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    json_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(result), encoding="utf-8")


def _price_quality_summary(group: pd.DataFrame, *, asset: str, threshold: float, long_flat_run_days: int) -> dict[str, Any]:
    if group.empty:
        return {
            "rows": 0,
            "duplicate_dates": 0,
            "missing_close": 0,
            "non_positive_prices": 0,
            "extreme_return_count": 0,
            "long_flat_run_count": 0,
            "coverage_start": None,
            "coverage_end": None,
            "timezone_normalized": True,
        }
    close = pd.to_numeric(group["close"], errors="coerce") if "close" in group.columns else pd.Series(dtype=float)
    returns = close.pct_change()
    flat_runs = _long_flat_runs(close, min_length=long_flat_run_days)
    return {
        "rows": int(len(group)),
        "duplicate_dates": int(group.duplicated(["ts", "asset"]).sum()),
        "missing_close": int(close.isna().sum()),
        "non_positive_prices": int((close <= 0).sum()),
        "extreme_return_count": int((returns.abs() > threshold).sum()),
        "long_flat_run_count": int(flat_runs),
        "coverage_start": str(group["ts"].min()) if "ts" in group else None,
        "coverage_end": str(group["ts"].max()) if "ts" in group else None,
        "timezone_normalized": bool((group["ts"] == group["ts"].dt.normalize()).all()) if "ts" in group else False,
    }


def _long_flat_runs(series: pd.Series, *, min_length: int) -> int:
    values = pd.to_numeric(series, errors="coerce")
    run_lengths = []
    current = 1
    previous = object()
    for value in values:
        if pd.notna(value) and value == previous:
            current += 1
        else:
            if current >= min_length:
                run_lengths.append(current)
            current = 1
        previous = value
    if current >= min_length:
        run_lengths.append(current)
    return len(run_lengths)


def _load_provenance(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    if isinstance(payload, dict) and isinstance(payload.get("series"), list):
        return [dict(item) for item in payload["series"]]
    return []


def _check_provenance(*, provenance: list[dict[str, Any]], path: Path, warnings: list[dict[str, str]]) -> None:
    if not provenance:
        _warn(warnings, "provenance", f"local provenance missing_or_empty: {path}")
        return
    for item in provenance:
        label = str(item.get("asset") or item.get("series_id") or "unknown")
        missing = [field for field in REQUIRED_PROVENANCE_FIELDS if field not in item]
        for field in missing:
            _warn(warnings, "provenance", f"{label}: missing provenance field `{field}`")
        source = str(item.get("source", "")).lower()
        if "yahoo" in source:
            _warn(warnings, "licensing", f"{label}: Yahoo local_research_only; redistribution_allowed=false; publication_grade=false; licensing_review_required=true")
        if "lbma" in source or "ice" in source:
            _warn(warnings, "licensing", f"{label}: LBMA/ICE licensing_review_required; redistribution_allowed=false unless explicitly licensed")
        if "baa" in source and "aaa" in source:
            _warn(warnings, "credit_proxy", f"{label}: proxy_type=BAA_MINUS_AAA; not_equivalent_to=ICE_BofA_HY_OAS; fill_method=business_daily_forward_fill")


def _check_local_source_provenance_configs(*, market_config_path: Path, macro_config_path: Path, provenance: list[dict[str, Any]], warnings: list[dict[str, str]]) -> None:
    provenance_assets = {str(item.get("asset", "")) for item in provenance}
    market_raw = _parse_simple_yaml(market_config_path.read_text()) if market_config_path.exists() else {}
    macro_raw = _parse_simple_yaml(macro_config_path.read_text()) if macro_config_path.exists() else {}
    for asset, values in market_raw.get("assets", {}).items():
        if values.get("source") == "local_csv" and asset not in provenance_assets:
            _warn(warnings, "provenance", f"{asset}: local source configured but missing from LOCAL_DATA_PROVENANCE")
    if macro_raw.get("series", {}).get("BAMLH0A0HYM2", {}).get("source") == "local_csv":
        labels = provenance_assets | {str(item.get("series_id", "")) for item in provenance}
        if "HY_OAS_PROXY" not in labels and "BAMLH0A0HYM2" not in labels:
            _warn(warnings, "provenance", "BAMLH0A0HYM2: local credit proxy configured but missing from LOCAL_DATA_PROVENANCE")


def _readiness_metrics(*, market: pd.DataFrame, stress: pd.DataFrame, provenance: list[dict[str, Any]]) -> dict[str, Any]:
    prepared_market = _prepare_ts(market)
    prepared_stress = _prepare_ts(stress)
    spx = prepared_market[prepared_market.get("asset") == "SPX"] if not prepared_market.empty and "asset" in prepared_market.columns else pd.DataFrame()
    stress_non_null = int(prepared_stress["cross_asset_stress_score"].notna().sum()) if not prepared_stress.empty and "cross_asset_stress_score" in prepared_stress else 0
    stress_rows = int(len(prepared_stress))
    return {
        "has_spx_long_history": bool(not spx.empty and spx["ts"].min() <= pd.Timestamp("1930-01-01", tz="UTC") and spx["ts"].max() >= pd.Timestamp("2020-01-01", tz="UTC")),
        "has_financial_stress_daily": bool(stress_rows > 0),
        "has_local_provenance": bool(provenance),
        "cross_asset_non_null_ratio": float(stress_non_null / stress_rows) if stress_rows else 0.0,
        "stress_rows": stress_rows,
        "cross_asset_non_null_rows": stress_non_null,
        "spx_coverage_start": str(spx["ts"].min()) if not spx.empty else None,
        "spx_coverage_end": str(spx["ts"].max()) if not spx.empty else None,
    }


def _prepare_ts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "ts" not in frame.columns:
        return frame
    working = frame.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    return working


def _asset_window_drawdown(frame: pd.DataFrame, asset: str) -> float:
    if frame.empty or "asset" not in frame.columns:
        return float("nan")
    group = frame[frame["asset"] == asset].sort_values("ts")
    if group.empty:
        return float("nan")
    if "drawdown_60d" in group.columns and group["drawdown_60d"].notna().any():
        return float(group["drawdown_60d"].min())
    return _asset_window_move(group, asset, [])


def _asset_window_move(frame: pd.DataFrame, asset: str, missing: list[str]) -> float:
    if frame.empty or "asset" not in frame.columns:
        missing.append(asset)
        return float("nan")
    group = frame[frame["asset"] == asset].sort_values("ts")
    if group.empty or "close" not in group.columns:
        missing.append(asset)
        return float("nan")
    close = pd.to_numeric(group["close"], errors="coerce").dropna()
    if len(close) < 2:
        missing.append(asset)
        return float("nan")
    return float(close.iloc[-1] / close.iloc[0] - 1.0)


def _macro_window_max(frame: pd.DataFrame, series_id: str, missing: list[str], label: str) -> float:
    group = frame[frame.get("series_id") == series_id] if not frame.empty and "series_id" in frame.columns else pd.DataFrame()
    if group.empty:
        missing.append(label)
        return float("nan")
    return float(pd.to_numeric(group["value"], errors="coerce").max())


def _macro_window_change(frame: pd.DataFrame, series_id: str, missing: list[str], label: str) -> float:
    group = frame[frame.get("series_id") == series_id].sort_values("ts") if not frame.empty and "series_id" in frame.columns else pd.DataFrame()
    if group.empty:
        missing.append(label)
        return float("nan")
    values = pd.to_numeric(group["value"], errors="coerce").dropna()
    if len(values) < 2:
        missing.append(label)
        return float("nan")
    return float(values.iloc[-1] - values.iloc[0])


def _stress_window_max(frame: pd.DataFrame, missing: list[str]) -> float:
    if frame.empty or "cross_asset_stress_score" not in frame.columns:
        missing.append("cross_asset_stress_score")
        return float("nan")
    return float(pd.to_numeric(frame["cross_asset_stress_score"], errors="coerce").max())


def _markdown(result: ReadinessResult) -> str:
    lines = [
        "# Formal Research Readiness",
        "",
        f"status: `{result.status}`",
        f"can_run_exploratory_formal_batch: `{str(result.can_run_exploratory_formal_batch).lower()}`",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in result.metrics.items())
    lines.extend(["", "## Warning Counts", "", "| category | count |", "|---|---:|"])
    if result.warning_counts:
        lines.extend(f"| {category} | {count} |" for category, count in sorted(result.warning_counts.items()))
    else:
        lines.append("| none | 0 |")
    lines.extend(["", "## Crisis Sanity Summary", "", "| event | SPX max drawdown | VIX max | DXY move | Gold move | credit proxy change | stress max | missing |", "|---|---:|---:|---:|---:|---:|---:|---|"])
    for item in result.crisis_summaries:
        lines.append(
            f"| {item['event_name']} | {_fmt(item['spx_max_drawdown'])} | {_fmt(item['vix_max'])} | {_fmt(item['dxy_move'])} | "
            f"{_fmt(item['gold_move'])} | {_fmt(item['credit_proxy_change'])} | {_fmt(item['cross_asset_stress_score_max'])} | "
            f"{', '.join(item['missing_component_list']) or 'none'} |"
        )
    lines.extend(["", "## Stress Sanity", "", "| check | max stress | elevated |", "|---|---:|---:|"])
    for item in result.stress_sanity:
        lines.append(f"| {item['label']} | {_fmt(item['max_cross_asset_stress_score'])} | {item['elevated']} |")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning['category']}` {warning['message']}" for warning in result.warnings)
    lines.extend(["", "## Interpretation", "", "This report is a readiness gate only. It does not make causal claims."])
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    try:
        if pd.isna(value):
            return "nan"
        return f"{float(value):.4f}"
    except Exception:
        return str(value)


def _warn(warnings: list[dict[str, str]], category: str, message: str) -> None:
    warnings.append({"category": category, "message": message})


def _resolve(root: Path, path: str | Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
