from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from astro_daily.config import _parse_simple_yaml
from research.io import read_aspect_chunk_events, read_aspect_chunk_windows, read_optional_table


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
    aspect_inputs = raw.get("aspect_inputs", {})
    families = raw.get("event_families", {})
    overlap = raw.get("overlap", {})
    warnings = []

    windows = read_optional_table(_resolve(root_path, str(inputs.get("astro_event_windows_path", ""))))
    aspect_frames = _load_aspect_inputs(aspect_inputs, root_path=root_path)
    aspect_windows = aspect_frames["windows"]
    aspect_events = aspect_frames["events"]
    if not aspect_windows.empty:
        windows = pd.concat([windows, aspect_windows], ignore_index=True) if not windows.empty else aspect_windows
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
    rows.extend(_aspect_events(aspect_events, dataset_id=dataset_id, calc_version=calc_version))
    rows.extend(_macro_core_cluster_events(aspect_events, aspect_inputs=aspect_inputs, dataset_id=dataset_id, calc_version=calc_version))
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
        events["exact_ts"] = pd.to_datetime(events["exact_ts"], utc=True)
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
    if "exact_ts" not in working.columns:
        return []
    working["exact_ts"] = pd.to_datetime(working["exact_ts"], utc=True)
    working = working[working["aspect_name"].notna()]
    rows = []
    for row in working.itertuples(index=False):
        body_a = str(getattr(row, "body_a", "") or "").title()
        body_b = str(getattr(row, "body_b", "") or "").title()
        aspect = str(getattr(row, "aspect_name", "")).lower()
        pair = {body_a, body_b}
        if pair == {"Mars", "Saturn"} and aspect in {"conjunction", "square", "opposition"}:
            family = "mars_saturn_hard_aspect"
        else:
            family = "macro_core_aspect"
        source_event_id = str(getattr(row, "event_id", "")) or _aspect_event_id(body_a, body_b, aspect, getattr(row, "exact_ts"))
        rows.append(
            _row(
                event_ts=pd.to_datetime(getattr(row, "exact_ts"), utc=True).normalize(),
                event_id=f"{family}_{source_event_id}",
                event_family=family,
                event_type=f"{_pair_slug(body_a, body_b)}_{aspect}",
                source_table="astro_aspect_events",
                source_event_id=source_event_id,
                body_a=body_a,
                body_b=body_b,
                aspect_name=aspect,
                profile=str(getattr(row, "profile", "macro_core")),
                event_strength=1.0,
                cluster_count=1,
                dataset_id=dataset_id,
                calc_version=calc_version,
                exact_ts=getattr(row, "exact_ts", None),
            )
        )
    return rows


def _macro_core_cluster_events(aspect_events: pd.DataFrame, *, aspect_inputs: dict, dataset_id: str, calc_version: str) -> list[dict]:
    if aspect_events.empty:
        return []
    macro_config = aspect_inputs.get("macro_core", {}) if isinstance(aspect_inputs, dict) else {}
    window_days_values = [int(value) for value in _split_raw(macro_config.get("cluster_window_days", "14"))]
    percentile = float(macro_config.get("cluster_percentile", 0.90))
    merge_days = int(macro_config.get("cluster_merge_days", 7))
    working = aspect_events.copy()
    working["exact_date"] = pd.to_datetime(working["exact_ts"], utc=True).dt.normalize()
    working = working[(working["exact_date"] >= pd.Timestamp("1926-01-01", tz="UTC")) & (working["exact_date"] <= pd.Timestamp("2025-12-31", tz="UTC"))]
    if working.empty:
        return []
    rows: list[dict] = []
    for window_days in window_days_values:
        counts = _cluster_counts(working["exact_date"], window_days=window_days)
        if counts.empty:
            continue
        threshold = counts["count"].quantile(percentile)
        selected = counts[counts["count"] >= threshold].copy()
        peaks = _merge_cluster_days(selected, merge_days=merge_days)
        for row in peaks.itertuples(index=False):
            event_date = pd.Timestamp(row.ts)
            rows.append(
                _row(
                    event_ts=event_date,
                    event_id=f"macro_core_aspect_cluster_p{int(percentile * 100)}_{window_days}d_{event_date:%Y%m%d}",
                    event_family="macro_core_aspect_cluster",
                    event_type=f"macro_core_cluster_p{int(percentile * 100)}_{window_days}d",
                    source_table="astro_aspect_events",
                    source_event_id=f"macro_core_cluster_{window_days}d_{event_date:%Y%m%d}",
                    profile="macro_core",
                    event_strength=float(row.count),
                    cluster_count=int(row.count),
                    dataset_id=dataset_id,
                    calc_version=calc_version,
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


def _load_aspect_inputs(aspect_inputs: dict, *, root_path: Path) -> dict[str, pd.DataFrame]:
    all_events: list[pd.DataFrame] = []
    all_windows: list[pd.DataFrame] = []
    for profile_name, values in (aspect_inputs or {}).items():
        chunks_dir = values.get("aspect_chunks_dir")
        if not chunks_dir:
            continue
        root = _resolve(root_path, str(chunks_dir))
        events = read_aspect_chunk_events(root)
        windows = read_aspect_chunk_windows(root)
        profile = str(values.get("aspect_profile", profile_name))
        body_pairs = set(_normalize_pair(value) for value in _split_raw(values.get("body_pairs", "")))
        aspect_names = set(value.lower() for value in _split_raw(values.get("aspect_names", "")))
        events = _filter_aspects(events, body_pairs=body_pairs, aspect_names=aspect_names, profile=profile)
        windows = _filter_aspects(windows, body_pairs=body_pairs, aspect_names=aspect_names, profile=profile)
        if not events.empty:
            all_events.append(events)
        if not windows.empty:
            all_windows.append(windows)
    return {
        "events": pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame(),
        "windows": pd.concat(all_windows, ignore_index=True) if all_windows else pd.DataFrame(),
    }


def _filter_aspects(frame: pd.DataFrame, *, body_pairs: set[str], aspect_names: set[str], profile: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    if "body_a" in working.columns and "body_b" in working.columns and body_pairs:
        pairs = working.apply(lambda row: _normalize_pair(f"{row.get('body_a', '')}_{row.get('body_b', '')}"), axis=1)
        working = working[pairs.isin(body_pairs)]
    if "aspect_name" in working.columns and aspect_names:
        working = working[working["aspect_name"].astype(str).str.lower().isin(aspect_names)]
    if not working.empty:
        working["profile"] = profile
    return working.reset_index(drop=True)


def _cluster_counts(exact_dates: pd.Series, *, window_days: int) -> pd.DataFrame:
    dates = pd.to_datetime(exact_dates, utc=True).dt.normalize().dropna()
    if dates.empty:
        return pd.DataFrame(columns=["ts", "count"])
    start = dates.min()
    end = dates.max()
    daily = pd.Series(0, index=pd.date_range(start, end, freq="D", tz="UTC"), dtype=float)
    event_counts = dates.value_counts()
    daily.loc[event_counts.index] = event_counts.astype(float)
    counts = daily.rolling(window_days * 2 + 1, center=True, min_periods=1).sum()
    return pd.DataFrame({"ts": counts.index, "count": counts.astype(int).to_numpy()})


def _merge_cluster_days(selected: pd.DataFrame, *, merge_days: int) -> pd.DataFrame:
    if selected.empty:
        return selected
    working = selected.sort_values(["ts", "count"]).reset_index(drop=True)
    groups: list[pd.DataFrame] = []
    current: list[pd.Series] = []
    previous_ts = None
    for _, row in working.iterrows():
        if previous_ts is None or (row["ts"] - previous_ts).days <= merge_days:
            current.append(row)
        else:
            groups.append(pd.DataFrame(current))
            current = [row]
        previous_ts = row["ts"]
    if current:
        groups.append(pd.DataFrame(current))
    peaks = []
    for group in groups:
        peak = group.sort_values(["count", "ts"], ascending=[False, True]).iloc[0]
        peaks.append({"ts": peak["ts"], "count": int(peak["count"])})
    return pd.DataFrame(peaks)


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


def _split_raw(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _normalize_pair(value: str) -> str:
    parts = [part.strip().title() for part in str(value).replace("-", "_").split("_") if part.strip()]
    return "_".join(sorted(parts))


def _pair_slug(body_a: str, body_b: str) -> str:
    return "_".join(part.lower() for part in sorted((body_a, body_b)))


def _aspect_event_id(body_a: str, body_b: str, aspect: str, exact_ts) -> str:
    ts = pd.to_datetime(exact_ts, utc=True)
    return f"{_pair_slug(body_a, body_b)}_{aspect}_{ts:%Y%m%d%H%M}"


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
