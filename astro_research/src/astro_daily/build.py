from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .angle_math import normalize_360
from .aspects import (
    AspectEvent,
    active_major_aspects,
    aspect_cluster_count,
    aspect_event_rows,
    aspect_event_windows,
    aspect_regime,
    scan_aspect_events,
)
from .calendar import daily_datetimes, day_count, utc_midnight
from .config import AstroDailyConfig
from .ephemeris_backend import EphemerisBackend, PositionRecord
from .facts import feature_rows_to_facts, position_to_row
from .moon_phase import MoonPhaseEvent, daily_moon_phase, moon_phase_event_rows, moon_phase_event_windows, scan_moon_phase_events
from .positions import build_daily_positions
from .retrograde import (
    ACTIVE_RETROGRADE_PHASES,
    RetrogradeCycle,
    StationEvent,
    build_station_event_windows,
    daily_retrograde_state,
    pair_retrograde_cycles,
    scan_station_events,
    station_cluster_count,
)
from .swiss_ephemeris_backend import SwissEphemerisBackend


WIDE_RETROGRADE_BODIES = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")


@dataclass(frozen=True)
class AstroDailyDataset:
    positions: list[dict]
    retrograde_cycles: list[dict]
    aspect_events: list[dict]
    moon_phase_events: list[dict]
    event_windows: list[dict]
    daily_features: list[dict]
    daily_facts: list[dict]
    station_events: list[StationEvent]
    exact_aspect_events: list[AspectEvent]
    exact_moon_phase_events: list[MoonPhaseEvent]
    cycles: list[RetrogradeCycle]

    @property
    def summary(self) -> dict:
        return {
            "position_rows": len(self.positions),
            "retrograde_cycles": len(self.retrograde_cycles),
            "aspect_events": len(self.aspect_events),
            "moon_phase_events": len(self.moon_phase_events),
            "event_window_rows": len(self.event_windows),
            "daily_feature_rows": len(self.daily_features),
            "daily_fact_rows": len(self.daily_facts),
            "station_events": len(self.station_events),
        }


def build_astro_daily_dataset(
    config: AstroDailyConfig,
    *,
    start: date | None = None,
    end: date | None = None,
    backend: EphemerisBackend | None = None,
) -> AstroDailyDataset:
    target_start = start or config.dataset.target_start
    target_end = end or config.dataset.target_end
    if target_end < target_start:
        raise ValueError("end must be on or after start.")

    backend = backend or SwissEphemerisBackend()
    calc_start_ts = utc_midnight(target_start) - pd.Timedelta(days=config.dataset.buffer_days).to_pytimedelta()
    calc_end_ts = utc_midnight(target_end) + pd.Timedelta(days=config.dataset.buffer_days, hours=23).to_pytimedelta()

    station_events = scan_station_events(
        backend=backend,
        bodies=config.retrograde_bodies,
        start_ts=calc_start_ts,
        end_ts=calc_end_ts,
        step_hours=config.retrograde.station_scan_step_hours,
        tolerance_seconds=config.retrograde.station_refine_tolerance_seconds,
    )
    cycles = pair_retrograde_cycles(
        station_events,
        station_phase_days=config.retrograde.station_phase_days,
        pre_post_window_days=config.retrograde.pre_post_window_days,
    )
    moon_phase_events = scan_moon_phase_events(
        backend=backend,
        start_ts=calc_start_ts,
        end_ts=calc_end_ts,
        step_hours=12,
        tolerance_seconds=120,
    )
    aspect_events = scan_aspect_events(
        backend=backend,
        bodies=config.aspect_bodies,
        major_aspects=config.major_aspects,
        start_ts=calc_start_ts,
        end_ts=calc_end_ts,
        step_hours=12,
        tolerance_seconds=120,
    )

    timestamps = tuple(daily_datetimes(target_start, target_end))
    position_records = build_daily_positions(backend=backend, bodies=config.position_bodies, timestamps=timestamps)
    position_rows = [
        position_to_row(
            record,
            dataset_id=config.dataset.dataset_id,
            calc_version=config.dataset.calc_version,
            oob_threshold_deg=config.oob_threshold_deg,
        )
        for record in position_records
    ]
    positions_by_day = _positions_by_day(position_records)
    daily_features = [
        _build_feature_row(
            ts=ts,
            position_by_body=positions_by_day[ts.date()],
            config=config,
            station_events=station_events,
            aspect_events=aspect_events,
            cycles=cycles,
        )
        for ts in timestamps
    ]
    cycle_rows = [_cycle_to_row(cycle, dataset_id=config.dataset.dataset_id, calc_version=config.dataset.calc_version) for cycle in cycles]
    aspect_rows = aspect_event_rows(aspect_events, dataset_id=config.dataset.dataset_id, calc_version=config.dataset.calc_version)
    moon_rows = moon_phase_event_rows(moon_phase_events, dataset_id=config.dataset.dataset_id, calc_version=config.dataset.calc_version)
    window_rows = build_station_event_windows(
        station_events,
        dataset_id=config.dataset.dataset_id,
        calc_version=config.dataset.calc_version,
        window_days_values=(7, 14, config.retrograde.event_study_window_days),
    )
    window_rows.extend(
        moon_phase_event_windows(
            moon_phase_events,
            dataset_id=config.dataset.dataset_id,
            calc_version=config.dataset.calc_version,
            window_days_values=(3, 7),
        )
    )
    window_rows.extend(
        aspect_event_windows(
            aspect_events,
            dataset_id=config.dataset.dataset_id,
            calc_version=config.dataset.calc_version,
            window_days_values=tuple(config.clusters.aspect_cluster_windows_days),
        )
    )
    window_rows = [row for row in window_rows if target_start <= pd.Timestamp(row["ts"]).date() <= target_end]
    fact_rows = feature_rows_to_facts(daily_features, dataset_id=config.dataset.dataset_id, calc_version=config.dataset.calc_version)
    return AstroDailyDataset(
        positions=position_rows,
        retrograde_cycles=cycle_rows,
        aspect_events=aspect_rows,
        moon_phase_events=moon_rows,
        event_windows=window_rows,
        daily_features=daily_features,
        daily_facts=fact_rows,
        station_events=station_events,
        exact_aspect_events=aspect_events,
        exact_moon_phase_events=moon_phase_events,
        cycles=cycles,
    )


def export_dataset(dataset: AstroDailyDataset, output_dir: str | Path, *, write_parquet: bool = True) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        "astro_daily_positions": dataset.positions,
        "astro_retrograde_cycles": dataset.retrograde_cycles,
        "astro_aspect_events": dataset.aspect_events,
        "astro_moon_phase_events": dataset.moon_phase_events,
        "astro_event_windows": dataset.event_windows,
        "astro_daily_features": dataset.daily_features,
        "astro_daily_facts": dataset.daily_facts,
    }
    paths: dict[str, Path] = {}
    for table, rows in tables.items():
        frame = pd.DataFrame(rows)
        csv_path = output / f"{table}.csv"
        frame.to_csv(csv_path, index=False)
        paths[f"{table}.csv"] = csv_path
        if write_parquet:
            parquet_path = output / f"{table}.parquet"
            try:
                frame.to_parquet(parquet_path, index=False)
            except ImportError:
                continue
            paths[f"{table}.parquet"] = parquet_path
    return paths


def validate_dataset(dataset: AstroDailyDataset, *, start: date, end: date, position_bodies: Iterable[str]) -> tuple[str, ...]:
    warnings: list[str] = []
    expected_days = day_count(start, end)
    if len(dataset.daily_features) != expected_days:
        warnings.append(f"daily_features row count mismatch: expected={expected_days} actual={len(dataset.daily_features)}")
    expected_positions = expected_days * len(tuple(position_bodies))
    if len(dataset.positions) != expected_positions:
        warnings.append(f"positions row count mismatch: expected={expected_positions} actual={len(dataset.positions)}")
    feature_keys = {(row["ts"], row["dataset_id"]) for row in dataset.daily_features}
    if len(feature_keys) != len(dataset.daily_features):
        warnings.append("duplicate astro_daily_features keys detected")
    position_keys = {(row["ts"], row["dataset_id"], row["body"]) for row in dataset.positions}
    if len(position_keys) != len(dataset.positions):
        warnings.append("duplicate astro_daily_positions keys detected")
    for cycle in dataset.cycles:
        if not cycle.station_in_ts < cycle.station_out_ts:
            warnings.append(f"invalid cycle order: {cycle.cycle_id}")
        if cycle.retrograde_days <= 0:
            warnings.append(f"invalid retrograde_days: {cycle.cycle_id}")
    return tuple(warnings)


def _positions_by_day(records: Iterable[PositionRecord]) -> dict[date, dict[str, PositionRecord]]:
    by_day: dict[date, dict[str, PositionRecord]] = {}
    for record in records:
        by_day.setdefault(record.ts.date(), {})[record.body] = record
    return by_day


def _build_feature_row(
    *,
    ts: datetime,
    position_by_body: dict[str, PositionRecord],
    config: AstroDailyConfig,
    station_events: list[StationEvent],
    aspect_events: list[AspectEvent],
    cycles: list[RetrogradeCycle],
) -> dict:
    day = ts.date()
    row: dict = {
        "ts": ts.astimezone(UTC),
        "dataset_id": config.dataset.dataset_id,
        "calc_version": config.dataset.calc_version,
    }
    active_bodies: list[str] = []
    for body in WIDE_RETROGRADE_BODIES:
        state = daily_retrograde_state(day, body, cycles, station_events)
        key = body.lower()
        row[f"{key}_phase"] = state.phase
        row[f"{key}_is_retrograde"] = state.is_retrograde
        row[f"{key}_days_since_station"] = state.days_since_station
        row[f"{key}_days_until_station"] = state.days_until_station
        row[f"{key}_cycle_id"] = state.cycle_id
        if state.phase in ACTIVE_RETROGRADE_PHASES:
            active_bodies.append(body)

    row["active_retrograde_count"] = len(active_bodies)
    row["active_retrograde_bodies"] = ",".join(active_bodies)
    for window_days in config.clusters.station_cluster_windows_days:
        row[f"station_cluster_count_{window_days}d"] = station_cluster_count(day, station_events, window_days)
    active_aspects = active_major_aspects(
        position_by_body,
        bodies=config.aspect_bodies,
        major_aspects=config.major_aspects,
        orbs=config.aspect_orbs_deg,
    )
    row["major_aspect_active_count"] = len(active_aspects)
    for window_days in config.clusters.aspect_cluster_windows_days:
        row[f"major_aspect_cluster_count_{window_days}d"] = aspect_cluster_count(day, aspect_events, window_days)

    moon_phase_name, moon_phase_angle_deg, moon_illumination_pct = daily_moon_phase(position_by_body)
    row["moon_phase_name"] = moon_phase_name
    row["moon_phase_angle_deg"] = moon_phase_angle_deg
    row["moon_illumination_pct"] = moon_illumination_pct

    row["jupiter_saturn_angle_deg"] = _angle_between(position_by_body["Jupiter"], position_by_body["Saturn"])
    row["jupiter_saturn_regime"] = aspect_regime(row["jupiter_saturn_angle_deg"], orbs=config.aspect_orbs_deg)
    row["mars_saturn_angle_deg"] = _angle_between(position_by_body["Mars"], position_by_body["Saturn"])
    row["mars_saturn_regime"] = aspect_regime(row["mars_saturn_angle_deg"], orbs=config.aspect_orbs_deg)
    return row


def _angle_between(first: PositionRecord, second: PositionRecord) -> float:
    return normalize_360(second.lon_deg - first.lon_deg)


def _cycle_to_row(cycle: RetrogradeCycle, *, dataset_id: str, calc_version: str) -> dict:
    return {
        "station_in_ts": cycle.station_in_ts,
        "dataset_id": dataset_id,
        "cycle_id": cycle.cycle_id,
        "body": cycle.body,
        "station_in_date_ts": utc_midnight(cycle.station_in_date),
        "station_out_ts": cycle.station_out_ts,
        "station_out_date_ts": utc_midnight(cycle.station_out_date),
        "retrograde_start_ts": cycle.station_in_ts,
        "retrograde_end_ts": cycle.station_out_ts,
        "pre_window_start_ts": utc_midnight(cycle.pre_window_start_date),
        "post_window_end_ts": utc_midnight(cycle.post_window_end_date),
        "retrograde_days": cycle.retrograde_days,
        "pre_post_window_days": cycle.pre_post_window_days,
        "station_phase_days": cycle.station_phase_days,
        "station_in_type": "direct_to_retrograde",
        "station_out_type": "retrograde_to_direct",
        "calc_version": calc_version,
        "source_note": "Station pairs refined from longitude speed sign changes.",
    }
