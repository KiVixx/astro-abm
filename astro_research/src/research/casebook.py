from __future__ import annotations

from pathlib import Path

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.io import read_optional_table


def build_casebook(config_path: str | Path, *, root: str | Path | None = None, output_dir: str | Path | None = None) -> list[Path]:
    root_path = Path(root or Path.cwd())
    raw = _parse_simple_yaml(Path(config_path).read_text())
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
        path.write_text(_case_markdown(row, nearby_events, nearby_market, nearby_stress, window_days))
        paths.append(path)
    return paths


def _case_markdown(row, events: pd.DataFrame, market: pd.DataFrame, stress: pd.DataFrame, window_days: int) -> str:
    event_counts = events["event_family"].value_counts().to_dict() if not events.empty else {}
    market_assets = sorted(market["asset"].dropna().unique().tolist()) if not market.empty and "asset" in market.columns else []
    stress_mean = stress["cross_asset_stress_score"].mean() if not stress.empty and "cross_asset_stress_score" in stress.columns else float("nan")
    return (
        f"# {row.event_name}\n\n"
        f"event_id: `{row.event_id}`\n\n"
        f"window: +/- {window_days} days\n\n"
        f"category: `{row.category}`\n\n"
        f"date_confidence: `{row.date_confidence}`\n\n"
        "## Market Coverage\n\n"
        f"assets: {', '.join(market_assets) if market_assets else 'none'}\n\n"
        "## Financial Stress\n\n"
        f"mean_cross_asset_stress_score: {stress_mean:.4f}\n\n"
        "## Astro Events\n\n"
        + ("\n".join(f"- {family}: {count}" for family, count in event_counts.items()) if event_counts else "- none")
        + "\n\n## Caveats\n\n- Descriptive casebook only; no causal claim is made.\n"
    )


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
