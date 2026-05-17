from __future__ import annotations

from pathlib import Path

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.io import read_optional_table


def build_casebook(config_path: str | Path, *, root: str | Path | None = None, output_dir: str | Path | None = None) -> list[Path]:
    root_path = Path(root or Path.cwd())
    raw = _parse_simple_yaml(Path(config_path).read_text())
    data_version = str(raw.get("dataset", {}).get("data_version", "crisis_casebook_v1"))
    inputs = raw.get("inputs", {})
    window_days = int(raw.get("window_days", 90))
    output = Path(output_dir or root_path / "astro_research/output/reports/casebook")
    output.mkdir(parents=True, exist_ok=True)
    catalog = pd.read_csv(_resolve(root_path, str(inputs.get("crisis_catalog_path", ""))))
    events = read_optional_table(_resolve(root_path, str(inputs.get("research_events_path", ""))))
    market = read_optional_table(_resolve(root_path, str(inputs.get("market_features_path", ""))))
    stress = read_optional_table(_resolve(root_path, str(inputs.get("financial_stress_path", ""))))
    for frame, column in ((events, "event_ts"), (market, "ts"), (stress, "ts")):
        if not frame.empty and column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], utc=True).dt.normalize()
    paths = []
    for row in catalog.itertuples(index=False):
        start = pd.Timestamp(row.start_date, tz="UTC")
        left = start - pd.Timedelta(days=window_days)
        right = start + pd.Timedelta(days=window_days)
        nearby_events = events[(events["event_ts"] >= left) & (events["event_ts"] <= right)] if not events.empty else pd.DataFrame()
        nearby_market = market[(market["ts"] >= left) & (market["ts"] <= right)] if not market.empty else pd.DataFrame()
        nearby_stress = stress[(stress["ts"] >= left) & (stress["ts"] <= right)] if not stress.empty else pd.DataFrame()
        path = output / f"{row.event_id}.md"
        path.write_text(
            _case_markdown(
                row,
                nearby_events,
                nearby_market,
                nearby_stress,
                window_days,
                data_version=data_version,
                input_availability=_input_availability(events=events, market=market, stress=stress),
            )
        )
        paths.append(path)
    return paths


def _case_markdown(
    row,
    events: pd.DataFrame,
    market: pd.DataFrame,
    stress: pd.DataFrame,
    window_days: int,
    *,
    data_version: str,
    input_availability: dict[str, bool],
) -> str:
    missing_components = _missing_case_components(events=events, market=market, stress=stress)
    lines = [
        f"# {row.event_name}",
        "",
        f"event_id: `{row.event_id}`",
        f"data_version: `{data_version}`",
        f"case_window: `+/- {window_days} days around {row.start_date}`",
        f"category: `{row.category}`",
        f"region: `{getattr(row, 'region', '')}`",
        f"date_confidence: `{row.date_confidence}`",
        "",
        "## Interpretation Boundary",
        "",
        "This case report is descriptive historical context only. It reviews overlap among curated crisis dates, market/macro stress features, and astro research events; it does not assert causality, prediction, investment advice, or a trading signal.",
        "",
        "## Input Availability",
        "",
        "| input | available | in_window_rows |",
        "|---|---:|---:|",
        f"| research_events | {input_availability['research_events']} | {len(events)} |",
        f"| market_features | {input_availability['market_features']} | {len(market)} |",
        f"| financial_stress_daily | {input_availability['financial_stress_daily']} | {len(stress)} |",
        "",
        "## Market Window Summary",
        "",
        _market_summary_table(market),
        "",
        "## Financial Stress Summary",
        "",
        _stress_summary_table(stress),
        "",
        "## Astro Event Summary",
        "",
        _event_summary_table(events),
        "",
        "## Review Notes",
        "",
    ]
    if missing_components:
        lines.extend(f"- missing_component: `{component}`" for component in missing_components)
    else:
        lines.append("- missing_component: `none`")
    lines.extend(
        [
            f"- catalog_source: `{getattr(row, 'source', '')}`",
            f"- catalog_notes: {getattr(row, 'notes', '')}",
            "",
            "## Caveats",
            "",
            "- Descriptive casebook only; no causal claim is made.",
            "- Local data caveats, proxy flags, and licensing limitations from the source registry/provenance still apply.",
            "- Missing inputs are reported as review gaps rather than silently filled.",
        ]
    )
    return "\n".join(lines) + "\n"


def _input_availability(*, events: pd.DataFrame, market: pd.DataFrame, stress: pd.DataFrame) -> dict[str, bool]:
    return {
        "research_events": not events.empty,
        "market_features": not market.empty,
        "financial_stress_daily": not stress.empty,
    }


def _missing_case_components(*, events: pd.DataFrame, market: pd.DataFrame, stress: pd.DataFrame) -> list[str]:
    missing = []
    if events.empty:
        missing.append("research_events")
    if market.empty:
        missing.append("market_features")
    else:
        assets = set(market["asset"].dropna()) if "asset" in market.columns else set()
        for asset in ("SPX", "VIX", "Gold", "DXY", "BTC"):
            if asset not in assets:
                missing.append(f"market_asset:{asset}")
    if stress.empty:
        missing.append("financial_stress_daily")
    elif "cross_asset_stress_score" not in stress.columns or stress["cross_asset_stress_score"].dropna().empty:
        missing.append("cross_asset_stress_score")
    return missing


def _market_summary_table(market: pd.DataFrame) -> str:
    header = "| asset | rows | start | end | min_drawdown_60d | max_realized_vol_20d | max_absret_percentile_252d |\n|---|---:|---|---|---:|---:|---:|"
    if market.empty or "asset" not in market.columns:
        return header + "\n| none | 0 |  |  | nan | nan | nan |"
    rows = [header]
    for asset, group in market.groupby("asset", sort=True):
        rows.append(
            "| "
            + " | ".join(
                [
                    str(asset),
                    str(len(group)),
                    _date_text(group["ts"].min()) if "ts" in group else "",
                    _date_text(group["ts"].max()) if "ts" in group else "",
                    _fmt(_series_min(group, "drawdown_60d")),
                    _fmt(_series_max(group, "realized_vol_20d")),
                    _fmt(_series_max(group, "abs_ret_rank_252d")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _stress_summary_table(stress: pd.DataFrame) -> str:
    header = "| metric | value |\n|---|---:|"
    if stress.empty:
        return header + "\n| rows | 0 |"
    rows = [
        header,
        f"| rows | {len(stress)} |",
        f"| mean_cross_asset_stress_score | {_fmt(_series_mean(stress, 'cross_asset_stress_score'))} |",
        f"| max_cross_asset_stress_score | {_fmt(_series_max(stress, 'cross_asset_stress_score'))} |",
        f"| max_component_count | {_fmt(_series_max(stress, 'component_count'))} |",
    ]
    if "stress_regime" in stress.columns:
        for regime, count in stress["stress_regime"].value_counts(dropna=False).sort_index().items():
            rows.append(f"| stress_regime:{regime} | {count} |")
    return "\n".join(rows)


def _event_summary_table(events: pd.DataFrame) -> str:
    header = "| event_family | source_table | rows | primary_rows |\n|---|---|---:|---:|"
    if events.empty or "event_family" not in events.columns:
        return header + "\n| none |  | 0 | 0 |"
    rows = [header]
    group_cols = ["event_family"]
    if "source_table" in events.columns:
        group_cols.append("source_table")
    for keys, group in events.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys, "")
        primary_rows = int(group["is_primary"].fillna(False).astype(bool).sum()) if "is_primary" in group.columns else 0
        rows.append(f"| {keys[0]} | {keys[1] if len(keys) > 1 else ''} | {len(group)} | {primary_rows} |")
    return "\n".join(rows)


def _series_min(frame: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(frame[column], errors="coerce").min()) if column in frame.columns else float("nan")


def _series_max(frame: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(frame[column], errors="coerce").max()) if column in frame.columns else float("nan")


def _series_mean(frame: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(frame[column], errors="coerce").mean()) if column in frame.columns else float("nan")


def _date_text(value) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _fmt(value: float) -> str:
    return "nan" if pd.isna(value) else f"{value:.4f}"


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
