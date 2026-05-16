from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EventSelection:
    event_type: str
    events: pd.DataFrame


def select_event_windows(
    *,
    event_type: str,
    group: dict[str, Any],
    window_name: str,
    astro_event_windows: pd.DataFrame,
    astro_daily_features: pd.DataFrame,
) -> EventSelection:
    if window_name == "core":
        return EventSelection(event_type=event_type, events=_select_core_events(event_type, group, astro_daily_features))
    if "," in window_name:
        window_days = max(abs(int(value.strip())) for value in window_name.split(",", 1))
        target_window_name = _window_label(group, window_days)
    else:
        target_window_name = window_name

    kind = str(group.get("kind", ""))
    if kind == "daily_feature_threshold":
        selected = _select_threshold_windows(event_type, group, astro_daily_features, window_days)
        return EventSelection(event_type=event_type, events=_shape_events(selected, event_type, window_name))

    windows = astro_event_windows.copy()
    if windows.empty:
        return EventSelection(event_type=event_type, events=_empty_events())
    windows["ts"] = pd.to_datetime(windows["ts"], utc=True).dt.normalize()
    windows["exact_date_ts"] = pd.to_datetime(windows["exact_date_ts"], utc=True).dt.normalize()
    selected = windows[windows["window_name"] == target_window_name]
    if kind == "station":
        body = str(group["body"]).lower()
        selected = selected[selected["event_type"].astype(str).str.startswith(f"{body}_")]
    elif kind == "aspect":
        selected = _filter_aspects(selected, str(group.get("body_pairs", "")))
    else:
        selected = selected.iloc[0:0]
    return EventSelection(event_type=event_type, events=_shape_events(selected, event_type, window_name))


def _window_label(group: dict[str, Any], window_days: int) -> str:
    if str(group.get("kind")) == "aspect":
        return f"aspect_pm_{window_days}d"
    return f"station_pm_{window_days}d"


def _filter_aspects(windows: pd.DataFrame, body_pairs: str) -> pd.DataFrame:
    pairs = {
        tuple(part.strip().lower() for part in pair.replace("/", "-").split("-", 1))
        for pair in body_pairs.split(",")
        if pair.strip()
    }
    if not pairs:
        return windows[windows["aspect_name"].notna()]
    keys = set()
    for a, b in pairs:
        keys.add((a, b))
        keys.add((b, a))
    return windows[
        windows.apply(
            lambda row: (str(row.get("body_a", "")).lower(), str(row.get("body_b", "")).lower()) in keys,
            axis=1,
        )
    ]


def _select_threshold_windows(event_type: str, group: dict[str, Any], features: pd.DataFrame, window_days: int) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    feature = str(group["feature"])
    minimum = float(group.get("min_value", 1))
    working = features.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    dates = working.loc[pd.to_numeric(working[feature], errors="coerce") >= minimum, "ts"].drop_duplicates()
    rows = []
    for exact_date in dates:
        event_id = f"{event_type}_{exact_date:%Y%m%d}_pm{window_days}d"
        for rel_day in range(-window_days, window_days + 1):
            rows.append(
                {
                    "ts": exact_date + timedelta(days=rel_day),
                    "event_id": event_id,
                    "exact_date_ts": exact_date,
                    "rel_day": rel_day,
                    "window_name": f"feature_pm_{window_days}d",
                }
            )
    return pd.DataFrame(rows)


def _select_core_events(event_type: str, group: dict[str, Any], features: pd.DataFrame) -> pd.DataFrame:
    if features.empty or str(group.get("kind")) != "station":
        return _empty_events()
    body = str(group["body"]).lower()
    phase_col = f"{body}_phase"
    cycle_col = f"{body}_cycle_id"
    if phase_col not in features.columns:
        return _empty_events()
    working = features.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    selected = working[working[phase_col] == "retrograde_core"].copy()
    if selected.empty:
        return _empty_events()
    if cycle_col in selected.columns:
        selected["event_id"] = selected[cycle_col].fillna(f"{event_type}_core")
    else:
        selected["event_id"] = f"{event_type}_core"
    selected["exact_date_ts"] = selected.groupby("event_id")["ts"].transform("min")
    selected["rel_day"] = (selected["ts"] - selected["exact_date_ts"]).dt.days
    selected["window_name"] = "core"
    return selected[["ts", "event_id", "exact_date_ts", "rel_day", "window_name"]]


def _shape_events(frame: pd.DataFrame, event_type: str, requested_window: str) -> pd.DataFrame:
    if frame.empty:
        return _empty_events()
    selected = frame[["ts", "event_id", "exact_date_ts", "rel_day", "window_name"]].copy()
    selected["event_type"] = event_type
    selected["requested_window"] = requested_window
    return selected.drop_duplicates(["ts", "event_id"]).reset_index(drop=True)


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=["ts", "event_id", "exact_date_ts", "rel_day", "window_name", "event_type", "requested_window"])
