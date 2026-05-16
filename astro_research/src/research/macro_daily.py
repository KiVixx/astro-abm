from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from market_daily.providers.fred import FREDProvider
from market_daily.providers.local_csv import LocalCSVProvider


MACRO_COLUMNS = [
    "ts",
    "series_id",
    "source",
    "value",
    "original_frequency",
    "fill_method",
    "units",
    "data_version",
    "source_note",
]


@dataclass(frozen=True)
class MacroBuildResult:
    observations: pd.DataFrame
    warnings: tuple[str, ...]
    data_version: str
    diagnostics: pd.DataFrame


def build_macro_daily(config_path: str | Path, *, start: date, end: date) -> MacroBuildResult:
    config_path = Path(config_path)
    raw = _parse_simple_yaml(config_path.read_text())
    data_version = str(raw.get("dataset", {}).get("data_version", "macro_daily_v1"))
    provider = FREDProvider(provider_config={"api_key_env": raw.get("provider", {}).get("api_key_env", "FRED_API_KEY")})
    local_provider = LocalCSVProvider(root=config_path.parents[2])
    rows = []
    warnings = []
    for series_id, values in raw.get("series", {}).items():
        frame = pd.DataFrame()
        series_source = str(values.get("source", raw.get("provider", {}).get("source", "fred")))
        if series_source == "local_csv":
            frame = _read_local_fallback(series_id, values, provider=local_provider, start=start, end=end)
            if frame.empty:
                warnings.extend(frame.attrs.get("warnings", []))
                warnings.append(f"{series_id}: local_csv missing or empty.")
                continue
            warnings.extend(frame.attrs.get("warnings", []))
        elif provider.available:
            try:
                frame = provider.fetch_observations(series_id=series_id, start=start, end=end)
            except Exception as exc:
                warnings.append(f"{series_id}: {exc}")
        else:
            warnings.append(f"{series_id}: FRED API key is not configured.")
        if frame.empty:
            warnings.append(f"{series_id}: zero rows from FRED; marked unavailable.")
            frame = _read_local_fallback(series_id, values, provider=local_provider, start=start, end=end)
            if frame.empty:
                fallback_path = values.get("fallback_path")
                if fallback_path:
                    warnings.append(f"{series_id}: fallback local_csv missing or empty: {fallback_path}")
                warnings.extend(frame.attrs.get("warnings", []))
                continue
            warnings.append(f"{series_id}: using fallback local_csv.")
            warnings.extend(frame.attrs.get("warnings", []))
        frame["original_frequency"] = str(values.get("original_frequency", "daily"))
        frame["fill_method"] = str(values.get("fill_method", "none"))
        frame["units"] = str(values.get("units", ""))
        frame["data_version"] = data_version
        frame["source_note"] = frame.get("source_note", f"fred:{series_id}")
        rows.append(frame[MACRO_COLUMNS])
    observations = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=MACRO_COLUMNS)
    return MacroBuildResult(observations, tuple(warnings), data_version, provider.diagnostics_frame())


def export_macro_daily(result: MacroBuildResult, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "macro_daily_observations.csv"
    parquet_path = output / "macro_daily_observations.parquet"
    diagnostics_csv_path = output / "fred_diagnostics.csv"
    diagnostics_parquet_path = output / "fred_diagnostics.parquet"
    result.observations.to_csv(csv_path, index=False)
    result.observations.to_parquet(parquet_path, index=False)
    result.diagnostics.to_csv(diagnostics_csv_path, index=False)
    result.diagnostics.to_parquet(diagnostics_parquet_path, index=False)
    return {"csv": csv_path, "parquet": parquet_path, "diagnostics_csv": diagnostics_csv_path, "diagnostics_parquet": diagnostics_parquet_path}


def _read_local_fallback(series_id: str, values: dict[str, Any], *, provider: LocalCSVProvider, start: date, end: date) -> pd.DataFrame:
    if str(values.get("source", "")) != "local_csv" and str(values.get("fallback_source", "")) != "local_csv":
        return pd.DataFrame()
    fallback_path = values.get("path") or values.get("fallback_path")
    if not fallback_path:
        return pd.DataFrame()
    return provider.fetch_indicator_observations(series_id=series_id, path=str(fallback_path), start=start, end=end)
