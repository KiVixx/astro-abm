from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .calendar import day_count


def validate_snapshot(snapshot_dir: str | Path, *, start: date, end: date, dataset_id: str) -> str:
    snapshot = Path(snapshot_dir)
    lines = ["# Astro Daily Validation", "", f"Dataset: `{dataset_id}`", f"Range: {start} -> {end}"]
    expected_days = day_count(start, end)
    features = _read(snapshot / "astro_daily_features.csv")
    positions = _read(snapshot / "astro_daily_positions.csv")
    facts = _read(snapshot / "astro_daily_facts.csv")
    cycles = _read(snapshot / "astro_retrograde_cycles.csv")
    aspects = _read(snapshot / "astro_aspect_events.csv")
    moon_phases = _read(snapshot / "astro_moon_phase_events.csv")
    windows = _read(snapshot / "astro_event_windows.csv")

    lines.extend(
        [
            "",
            "## Row Counts",
            f"- astro_daily_features: {len(features)}",
            f"- astro_daily_positions: {len(positions)}",
            f"- astro_daily_facts: {len(facts)}",
            f"- astro_retrograde_cycles: {len(cycles)}",
            f"- astro_aspect_events: {len(aspects)}",
            f"- astro_moon_phase_events: {len(moon_phases)}",
            f"- astro_event_windows: {len(windows)}",
        ]
    )
    warnings = []
    if len(features) != expected_days:
        warnings.append(f"features expected {expected_days} rows, got {len(features)}")
    if not features.empty and features.duplicated(["ts", "dataset_id"]).any():
        warnings.append("duplicate astro_daily_features keys")
    if not positions.empty and positions.duplicated(["ts", "dataset_id", "body"]).any():
        warnings.append("duplicate astro_daily_positions keys")
    if not facts.empty and facts.duplicated(["ts", "dataset_id", "body", "metric"]).any():
        warnings.append("duplicate astro_daily_facts keys")
    if not windows.empty and windows.duplicated(["ts", "dataset_id", "event_id"]).any():
        warnings.append("duplicate astro_event_windows keys")
    if not aspects.empty and aspects.duplicated(["exact_ts", "dataset_id", "event_id"]).any():
        warnings.append("duplicate astro_aspect_events keys")
    if not moon_phases.empty and moon_phases.duplicated(["exact_ts", "dataset_id", "event_id"]).any():
        warnings.append("duplicate astro_moon_phase_events keys")
    if not positions.empty:
        bad_lon = positions[(positions["lon_deg"] < 0) | (positions["lon_deg"] >= 360)]
        if len(bad_lon):
            warnings.append(f"longitude range violations: {len(bad_lon)}")
        bad_declination = positions[(positions["declination_deg"] < -90) | (positions["declination_deg"] > 90)]
        if len(bad_declination):
            warnings.append(f"declination range violations: {len(bad_declination)}")
    if not cycles.empty:
        invalid_cycles = pd.to_datetime(cycles["station_in_ts"], utc=True) >= pd.to_datetime(cycles["station_out_ts"], utc=True)
        if invalid_cycles.any():
            warnings.append(f"invalid cycle order rows: {int(invalid_cycles.sum())}")

    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- none")
    return "\n".join(lines) + "\n"


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()
