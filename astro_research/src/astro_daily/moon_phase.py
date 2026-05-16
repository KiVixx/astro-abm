from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .angle_math import angular_diff_signed, normalize_360
from .calendar import utc_midnight
from .ephemeris_backend import EphemerisBackend
from .ephemeris_backend import PositionRecord


def moon_phase_angle(sun_lon_deg: float, moon_lon_deg: float) -> float:
    return normalize_360(moon_lon_deg - sun_lon_deg)


def moon_illumination_pct(elongation_deg: float) -> float:
    return (1.0 - math.cos(math.radians(elongation_deg))) / 2.0 * 100.0


def moon_phase_name(elongation_deg: float) -> str:
    angle = normalize_360(elongation_deg)
    if angle < 45 or angle >= 315:
        return "NewMoonZone"
    if angle < 135:
        return "FirstQuarterZone"
    if angle < 225:
        return "FullMoonZone"
    return "LastQuarterZone"


def daily_moon_phase(position_by_body: dict[str, PositionRecord]) -> tuple[str, float, float]:
    elongation = moon_phase_angle(position_by_body["Sun"].lon_deg, position_by_body["Moon"].lon_deg)
    return moon_phase_name(elongation), elongation, moon_illumination_pct(elongation)


@dataclass(frozen=True)
class MoonPhaseEvent:
    exact_ts: datetime
    phase_name: str
    elongation_deg: float

    @property
    def date(self):
        return self.exact_ts.astimezone(UTC).date()


MOON_PHASE_TARGETS = {
    "NewMoon": 0.0,
    "FirstQuarter": 90.0,
    "FullMoon": 180.0,
    "LastQuarter": 270.0,
}


def scan_moon_phase_events(
    *,
    backend: EphemerisBackend,
    start_ts: datetime,
    end_ts: datetime,
    step_hours: int = 12,
    tolerance_seconds: int = 120,
) -> list[MoonPhaseEvent]:
    events: list[MoonPhaseEvent] = []
    step = timedelta(hours=step_hours)
    for phase_name, target in MOON_PHASE_TARGETS.items():
        left_ts = start_ts
        left_value = _moon_phase_delta(backend, left_ts, target)
        while left_ts < end_ts:
            right_ts = min(left_ts + step, end_ts)
            right_value = _moon_phase_delta(backend, right_ts, target)
            if _crossed(left_value, right_value):
                exact_ts = _interpolate_zero(left_ts, right_ts, left_value, right_value)
                events.append(MoonPhaseEvent(exact_ts=exact_ts, phase_name=phase_name, elongation_deg=target))
            left_ts = right_ts
            left_value = right_value
    return _dedupe_events(sorted(events, key=lambda event: event.exact_ts))


def moon_phase_event_rows(events: list[MoonPhaseEvent], *, dataset_id: str, calc_version: str) -> list[dict]:
    return [
        {
            "exact_ts": event.exact_ts,
            "dataset_id": dataset_id,
            "event_id": f"{event.phase_name}_{event.exact_ts:%Y%m%d%H%M}",
            "phase_name": event.phase_name,
            "elongation_deg": event.elongation_deg,
            "calc_version": calc_version,
            "source_note": "Exact lunar phase refined from Sun-Moon elongation.",
        }
        for event in events
    ]


def moon_phase_event_windows(
    events: list[MoonPhaseEvent],
    *,
    dataset_id: str,
    calc_version: str,
    window_days_values: tuple[int, ...] = (3, 7),
) -> list[dict]:
    rows = []
    for event in events:
        base_event_id = f"{event.phase_name}_{event.exact_ts:%Y%m%d%H%M}"
        for window_days in window_days_values:
            for rel_day in range(-window_days, window_days + 1):
                day = event.date + timedelta(days=rel_day)
                rows.append(
                    {
                        "ts": utc_midnight(day),
                        "dataset_id": dataset_id,
                        "event_id": f"{base_event_id}_pm{window_days}d",
                        "event_type": "moon_phase",
                        "body": "Moon",
                        "body_a": "Sun",
                        "body_b": "Moon",
                        "aspect_name": None,
                        "phase_name": event.phase_name,
                        "exact_ts": event.exact_ts,
                        "exact_date_ts": utc_midnight(event.date),
                        "rel_day": rel_day,
                        "window_name": f"moon_phase_pm_{window_days}d",
                        "window_days": window_days,
                        "weight": 1.0,
                        "calc_version": calc_version,
                    }
                )
    return rows


def _moon_phase_delta(backend: EphemerisBackend, ts: datetime, target: float) -> float:
    sun = backend.get_position("Sun", ts)
    moon = backend.get_position("Moon", ts)
    return angular_diff_signed(moon_phase_angle(sun.lon_deg, moon.lon_deg), target)


def _crossed(left: float, right: float) -> bool:
    if abs(left - right) > 180.0:
        return False
    return right == 0.0 or (left < 0.0 < right) or (right < 0.0 < left)


def _refine_zero(fn, *, left_ts: datetime, right_ts: datetime, left_value: float, tolerance_seconds: int) -> datetime:
    left = left_ts
    right = right_ts
    left_v = left_value
    while (right - left).total_seconds() > tolerance_seconds:
        mid = left + (right - left) / 2
        mid_v = fn(mid)
        if _crossed(left_v, mid_v):
            right = mid
        else:
            left = mid
            left_v = mid_v
    return left + (right - left) / 2


def _interpolate_zero(left_ts: datetime, right_ts: datetime, left_value: float, right_value: float) -> datetime:
    denominator = abs(left_value) + abs(right_value)
    fraction = 0.5 if denominator == 0 else abs(left_value) / denominator
    return left_ts + (right_ts - left_ts) * fraction


def _dedupe_events(events: list[MoonPhaseEvent]) -> list[MoonPhaseEvent]:
    seen = set()
    deduped = []
    for event in events:
        key = (event.phase_name, event.exact_ts.strftime("%Y%m%d%H%M"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped
