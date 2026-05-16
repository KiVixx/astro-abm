from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd


COVERAGE_COLUMNS = [
    "ts",
    "asset",
    "source",
    "coverage_start_ts",
    "coverage_end_ts",
    "observation_count",
    "missing_count",
    "missing_pct",
    "calendar_expected_count",
    "calendar_missing_count",
    "frequency_adjusted_expected_count",
    "frequency_adjusted_missing_count",
    "frequency_adjusted_missing_pct",
    "first_valid_ts",
    "last_valid_ts",
    "frequency",
    "data_version",
    "source_note",
]


def build_asset_coverage(frame: pd.DataFrame, *, data_version: str, frequency: str = "daily") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=COVERAGE_COLUMNS)
    working = frame.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    rows = []
    for (asset, source), group in working.groupby(["asset", "source"], sort=False):
        valid = group.dropna(subset=["ts"])
        start = valid["ts"].min()
        end = valid["ts"].max()
        inferred_frequency = infer_asset_frequency(str(asset), default=frequency)
        calendar_expected = pd.date_range(start, end, freq="D", tz="UTC") if pd.notna(start) and pd.notna(end) else []
        adjusted_expected = expected_range(start, end, inferred_frequency) if pd.notna(start) and pd.notna(end) else []
        observation_count = int(valid["ts"].nunique())
        calendar_missing_count = max(len(calendar_expected) - observation_count, 0)
        adjusted_missing_count = max(len(adjusted_expected) - observation_count, 0)
        missing_count = adjusted_missing_count
        missing_pct = float(missing_count / len(adjusted_expected)) if len(adjusted_expected) else 0.0
        rows.append(
            {
                "ts": datetime.now(UTC),
                "asset": asset,
                "source": source,
                "coverage_start_ts": start,
                "coverage_end_ts": end,
                "observation_count": observation_count,
                "missing_count": missing_count,
                "missing_pct": missing_pct,
                "calendar_expected_count": len(calendar_expected),
                "calendar_missing_count": calendar_missing_count,
                "frequency_adjusted_expected_count": len(adjusted_expected),
                "frequency_adjusted_missing_count": adjusted_missing_count,
                "frequency_adjusted_missing_pct": missing_pct,
                "first_valid_ts": start,
                "last_valid_ts": end,
                "frequency": inferred_frequency,
                "data_version": data_version,
                "source_note": "coverage calculated from local build output",
            }
        )
    return pd.DataFrame(rows, columns=COVERAGE_COLUMNS)


def build_series_coverage(frame: pd.DataFrame, *, data_version: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=COVERAGE_COLUMNS)
    working = frame.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    rows = []
    for (series_id, source), group in working.groupby(["series_id", "source"], sort=False):
        frequency = str(group["original_frequency"].dropna().iloc[0]) if "original_frequency" in group.columns and group["original_frequency"].notna().any() else "daily"
        pseudo = group.assign(asset=series_id)
        rows.append(build_asset_coverage(pseudo, data_version=data_version, frequency=normalize_frequency(frequency)).iloc[0])
    return pd.DataFrame(rows, columns=COVERAGE_COLUMNS) if rows else pd.DataFrame(columns=COVERAGE_COLUMNS)


def write_coverage_report(coverage: pd.DataFrame, output_path) -> None:
    lines = [
        "# Market Data Coverage",
        "",
        "| asset | source | frequency | start | end | observations | calendar_missing | frequency_adjusted_missing | adjusted_missing_pct |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in coverage.itertuples(index=False):
        lines.append(
            f"| {row.asset} | {row.source} | {row.frequency} | {row.coverage_start_ts} | {row.coverage_end_ts} | "
            f"{row.observation_count} | {row.calendar_missing_count} | {row.frequency_adjusted_missing_count} | {row.frequency_adjusted_missing_pct:.4f} |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")


def infer_asset_frequency(asset: str, *, default: str = "daily") -> str:
    if asset in {"BTC", "ETH", "CBBTCUSD", "CBETHUSD"}:
        return "calendar_daily"
    if asset in {"USREC"}:
        return "monthly"
    if asset in {"NFCI"}:
        return "weekly"
    if asset in {"SPX", "NDX", "VIX", "US10Y", "US2Y", "DGS10", "DGS2", "VIXCLS", "NASDAQ100", "SP500", "HY_OAS", "BAMLH0A0HYM2"}:
        return "business_daily"
    return normalize_frequency(default)


def normalize_frequency(frequency: str) -> str:
    value = str(frequency or "daily").lower()
    if value in {"daily", "business", "business_daily", "trading_day"}:
        return "business_daily"
    if value in {"calendar", "calendar_daily", "crypto_daily"}:
        return "calendar_daily"
    if value.startswith("week"):
        return "weekly"
    if value.startswith("month"):
        return "monthly"
    return value


def expected_range(start, end, frequency: str):
    frequency = normalize_frequency(frequency)
    if frequency == "calendar_daily":
        return pd.date_range(start, end, freq="D", tz="UTC")
    if frequency == "business_daily":
        return pd.date_range(start, end, freq="B", tz="UTC")
    if frequency == "weekly":
        return pd.date_range(start, end, freq="W-FRI", tz="UTC")
    if frequency == "monthly":
        return pd.date_range(start, end, freq="MS", tz="UTC")
    return pd.date_range(start, end, freq="D", tz="UTC")
