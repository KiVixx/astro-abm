from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.io import read_aspect_chunk_windows, read_optional_table


RESEARCH_EVENT_COLUMNS = [
    "event_ts",
    "event_id",
    "event_family",
    "event_type",
    "source_table",
    "source_event_id",
    "body",
    "body_a",
    "body_b",
    "aspect_name",
    "phase_name",
    "profile",
    "exact_ts",
    "event_date_ts",
    "event_strength",
    "cluster_count",
    "is_primary",
    "is_overlapping",
    "eligible_for_event_study",
    "exclusion_reason",
    "dataset_id",
    "calc_version",
]


@dataclass(frozen=True)
class ResearchEventsResult:
    events: pd.DataFrame
    warnings: tuple[str, ...]
    data_version: str


def build_research_events(config_path: str | Path, *, root: str | Path | None = None) -> ResearchEventsResult:
    root_path = Path(root or Path.cwd())
    raw = _parse_simple_yaml(Path(config_path).read_text())
    data_version = str(raw.get("dataset", {}).get("data_version", "research_events_v1"))
    dataset_id = str(raw.get("dataset", {}).get("dataset_id", ""))
    calc_version = str(raw.get("dataset", {}).get("calc_version", "research_events_v1"))
    inputs = raw.get("inputs", {})
    families = raw.get("event_families", {})
    overlap = raw.get("overlap", {})
    warnings = []

    windows = read_optional_table(_resolve(root_path, str(inputs.get("astro_event_windows_path", ""))))
    chunks = read_aspect_chunk_windows(_resolve(root_path, str(inputs.get("aspect_chunks_dir", ""))))
    if not chunks.empty:
        windows = pd.concat([windows, chunks], ignore_index=True) if not windows.empty else chunks
    daily = read_optional_table(_resolve(root_path, str(inputs.get("astro_daily_features_path", ""))))
    moon = read_optional_table(_resolve(root_path, str(inputs.get("moon_phase_events_path", ""))))
    rows: list[dict[str, Any]] = []
    rows.extend(_station_events(windows, bodies=_split(families.get("station_bodies", "")), dataset_id=dataset_id, calc_version=calc_version))
    rows.extend(
        _station_cluster_events(
            daily,
            minimum=int(families.get("station_cluster_count_7d_gte", 2)),
            dataset_id=dataset_id,
            calc_version=calc_version,
        )
    )
    rows.extend(_aspect_events(windows, dataset_id=dataset_id, calc_version=calc_version))
    rows.extend(
        _active_retrograde_events(
            daily,
            minimum=int(families.get("active_retrograde_count_gte", 3)),
            dataset_id=dataset_id,
            calc_version=calc_version,
        )
    )
    rows.extend(_moon_events(moon, phases=_split(families.get("moon_phases", "NewMoon,FullMoon")), dataset_id=dataset_id, calc_version=calc_version))
    events = pd.DataFrame(rows, columns=RESEARCH_EVENT_COLUMNS)
    if not events.empty:
        events["event_ts"] = pd.to_datetime(events["event_ts"], utc=True).dt.normalize()
        events["event_date_ts"] = pd.to_datetime(events["event_date_ts"], utc=True).dt.normalize()
        events = events.sort_values(["event_family", "event_ts", "event_id"]).drop_duplicates(["event_ts", "event_id"])
        events = _apply_overlap_policy(events, policy=str(overlap.get("policy", "allow_overlap")), window_days=int(overlap.get("window_days", 7)))
    else:
        warnings.append("No research events generated.")
    return ResearchEventsResult(events, tuple(warnings), data_version)


def export_research_events(result: ResearchEventsResult, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "research_events.csv"
    parquet_path = output / "research_events.parquet"
    result.events.to_csv(csv_path, index=False)
    result.events.to_parquet(parquet_path, index=False)
    return {"csv": csv_path, "parquet": parquet_path}


def _station_events(windows: pd.DataFrame, *, bodies: list[str], dataset_id: str, calc_version: str) -> list[dict]:
    if windows.empty:
        return []
    working = windows.copy()
    working["rel_day"] = pd.to_numeric(working["rel_day"], errors="coerce")
    working = working[(working["rel_day"] == 0) & working["event_type"].astype(str).str.contains("_to_")]
    rows = []
    for row in working.itertuples(index=False):
        body = str(getattr(row, "body", "") or "").title()
        if bodies and body not in bodies:
            continue
        family = f"{body.lower()}_station"
        rows.append(
            _row(
                event_ts=getattr(row, "exact_date_ts"),
                event_id=f"{family}_{getattr(row, 'event_id')}",
                event_family=family,
                event_type=str(getattr(row, "event_type")),
                source_table="astro_event_windows",
                source_event_id=str(getattr(row, "event_id")),
                body=body,
                event_strength=1.0,
                cluster_count=1,
                dataset_id=dataset_id,
                calc_version=calc_version,
                exact_ts=getattr(row, "exact_ts", None),
            )
        )
    return rows


def _station_cluster_events(daily: pd.DataFrame, *, minimum: int, dataset_id: str, calc_version: str) -> list[dict]:
    if daily.empty or "station_cluster_count_7d" not in daily.columns:
        return []
    working = daily.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    selected = working[pd.to_numeric(working["station_cluster_count_7d"], errors="coerce") >= minimum]
    return [
        _row(
            event_ts=row.ts,
            event_id=f"station_cluster_{row.ts:%Y%m%d}",
            event_family="station_cluster",
            event_type="station_cluster_count_7d",
            source_table="astro_daily_features",
            source_event_id=f"station_cluster_{row.ts:%Y%m%d}",
            event_strength=float(row.station_cluster_count_7d),
            cluster_count=int(row.station_cluster_count_7d),
            dataset_id=dataset_id,
            calc_version=calc_version,
        )
        for row in selected.itertuples(index=False)
    ]


def _aspect_events(windows: pd.DataFrame, *, dataset_id: str, calc_version: str) -> list[dict]:
    if windows.empty:
        return []
    working = windows.copy()
    working["rel_day"] = pd.to_numeric(working["rel_day"], errors="coerce")
    working = working[(working["rel_day"] == 0) & working["aspect_name"].notna()]
    rows = []
    for row in working.itertuples(index=False):
        body_a = str(getattr(row, "body_a", "") or "").title()
        body_b = str(getattr(row, "body_b", "") or "").title()
        aspect = str(getattr(row, "aspect_name", ""))
        pair = {body_a, body_b}
        if pair == {"Mars", "Saturn"} and aspect in {"conjunction", "square", "opposition"}:
            family = "mars_saturn_hard_aspect"
        else:
            family = "macro_core_aspect"
        rows.append(
            _row(
                event_ts=getattr(row, "exact_date_ts"),
                event_id=f"{family}_{getattr(row, 'event_id')}",
                event_family=family,
                event_type=f"{body_a.lower()}_{body_b.lower()}_{aspect}",
                source_table="astro_event_windows",
                source_event_id=str(getattr(row, "event_id")),
                body_a=body_a,
                body_b=body_b,
                aspect_name=aspect,
                profile="macro_core",
                event_strength=1.0,
                cluster_count=1,
                dataset_id=dataset_id,
                calc_version=calc_version,
                exact_ts=getattr(row, "exact_ts", None),
            )
        )
    return rows


def _active_retrograde_events(daily: pd.DataFrame, *, minimum: int, dataset_id: str, calc_version: str) -> list[dict]:
    if daily.empty or "active_retrograde_count" not in daily.columns:
        return []
    working = daily.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    selected = working[pd.to_numeric(working["active_retrograde_count"], errors="coerce") >= minimum]
    return [
        _row(
            event_ts=row.ts,
            event_id=f"active_retrograde_count_{row.ts:%Y%m%d}",
            event_family="active_retrograde_count",
            event_type="active_retrograde_count",
            source_table="astro_daily_features",
            source_event_id=f"active_retrograde_count_{row.ts:%Y%m%d}",
            event_strength=float(row.active_retrograde_count),
            cluster_count=int(row.active_retrograde_count),
            dataset_id=dataset_id,
            calc_version=calc_version,
        )
        for row in selected.itertuples(index=False)
    ]


def _moon_events(moon: pd.DataFrame, *, phases: list[str], dataset_id: str, calc_version: str) -> list[dict]:
    if moon.empty:
        return []
    working = moon.copy()
    selected = working[working["phase_name"].isin(phases)]
    return [
        _row(
            event_ts=pd.to_datetime(row.exact_ts, utc=True).normalize(),
            event_id=f"moon_phase_{row.event_id}",
            event_family="moon_phase",
            event_type=str(row.phase_name),
            source_table="astro_moon_phase_events",
            source_event_id=str(row.event_id),
            body="Moon",
            phase_name=str(row.phase_name),
            event_strength=1.0,
            cluster_count=1,
            dataset_id=dataset_id,
            calc_version=calc_version,
            exact_ts=row.exact_ts,
        )
        for row in selected.itertuples(index=False)
    ]


def _apply_overlap_policy(events: pd.DataFrame, *, policy: str, window_days: int) -> pd.DataFrame:
    if policy == "allow_overlap" or events.empty:
        return events
    events = events.copy()
    events["is_primary"] = True
    events["is_overlapping"] = False
    last_primary: dict[str, pd.Timestamp] = {}
    for index, row in events.iterrows():
        previous = last_primary.get(row["event_family"])
        if previous is not None and abs((row["event_ts"] - previous).days) <= window_days:
            events.at[index, "is_overlapping"] = True
            if policy == "drop_overlapping_events":
                events.at[index, "eligible_for_event_study"] = False
                events.at[index, "exclusion_reason"] = "overlap_window"
            elif policy == "cluster_overlapping_events":
                events.at[index, "is_primary"] = False
                events.at[index, "eligible_for_event_study"] = False
                events.at[index, "exclusion_reason"] = "clustered_overlap"
        else:
            last_primary[row["event_family"]] = row["event_ts"]
    return events


def _row(**kwargs) -> dict:
    row = {column: None for column in RESEARCH_EVENT_COLUMNS}
    row.update(
        {
            "event_date_ts": kwargs.get("event_ts"),
            "is_primary": True,
            "is_overlapping": False,
            "eligible_for_event_study": True,
            "exclusion_reason": "",
        }
    )
    row.update(kwargs)
    return row


def _split(value: Any) -> list[str]:
    return [item.strip().title() for item in str(value or "").split(",") if item.strip()]


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
