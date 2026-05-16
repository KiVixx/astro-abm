from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations

from .angle_math import angular_diff_signed, angular_distance, normalize_360
from .calendar import utc_midnight
from .ephemeris_backend import EphemerisBackend, PositionRecord


def aspect_regime(angle_deg: float, *, orbs: dict[str, float] | None = None) -> str:
    orbs = orbs or {"conjunction": 8, "sextile": 4, "square": 6, "trine": 6, "opposition": 8}
    angle = normalize_360(angle_deg)
    checks = (
        ("conjunction_zone", 0.0, orbs.get("conjunction", 8)),
        ("sextile_zone", 60.0, orbs.get("sextile", 4)),
        ("waxing_square_zone", 90.0, orbs.get("square", 6)),
        ("trine_zone", 120.0, orbs.get("trine", 6)),
        ("opposition_zone", 180.0, orbs.get("opposition", 8)),
        ("waning_square_zone", 270.0, orbs.get("square", 6)),
    )
    for name, target, orb in checks:
        if angular_distance(angle, target) <= orb:
            return name
    return "none"


@dataclass(frozen=True)
class AspectEvent:
    exact_ts: datetime
    body_a: str
    body_b: str
    aspect_name: str
    aspect_deg: float
    exact_delta_deg: float
    relative_speed_deg_day: float
    applying_before: bool

    @property
    def date(self):
        return self.exact_ts.astimezone(UTC).date()


def active_major_aspects(
    position_by_body: dict[str, PositionRecord],
    *,
    bodies: tuple[str, ...],
    major_aspects: dict[str, int],
    orbs: dict[str, float],
) -> list[tuple[str, str, str]]:
    active = []
    for body_a, body_b in combinations(bodies, 2):
        if body_a not in position_by_body or body_b not in position_by_body:
            continue
        separation = normalize_360(position_by_body[body_b].lon_deg - position_by_body[body_a].lon_deg)
        for aspect_name, aspect_deg in major_aspects.items():
            if _aspect_distance(separation, aspect_deg) <= orbs.get(aspect_name, 0.0):
                active.append((body_a, body_b, aspect_name))
    return active


def scan_aspect_events(
    *,
    backend: EphemerisBackend,
    bodies: tuple[str, ...],
    major_aspects: dict[str, int],
    start_ts: datetime,
    end_ts: datetime,
    step_hours: int = 12,
    tolerance_seconds: int = 120,
) -> list[AspectEvent]:
    events: list[AspectEvent] = []
    for body_a, body_b in combinations(bodies, 2):
        events.extend(
            scan_aspect_events_for_pair(
                backend=backend,
                body_a=body_a,
                body_b=body_b,
                major_aspects=major_aspects,
                start_ts=start_ts,
                end_ts=end_ts,
                step_hours=step_hours,
                tolerance_seconds=tolerance_seconds,
            )
        )
    return _dedupe_aspect_events(sorted(events, key=lambda event: (event.exact_ts, event.body_a, event.body_b, event.aspect_name)))


def scan_aspect_events_for_pair(
    *,
    backend: EphemerisBackend,
    body_a: str,
    body_b: str,
    major_aspects: dict[str, int],
    start_ts: datetime,
    end_ts: datetime,
    step_hours: int = 12,
    tolerance_seconds: int = 120,
) -> list[AspectEvent]:
    body_a, body_b = ordered_body_pair(body_a, body_b)
    events: list[AspectEvent] = []
    step = timedelta(hours=step_hours)
    scan_times = _scan_times(start_ts, end_ts, step)
    longitudes = {
        body: [backend.get_position(body, ts).lon_deg for ts in scan_times]
        for body in (body_a, body_b)
    }
    separations = [
        normalize_360(second - first)
        for first, second in zip(longitudes[body_a], longitudes[body_b])
    ]
    for aspect_name, aspect_deg in major_aspects.items():
        for target_deg in _target_degrees(float(aspect_deg)):
            values = [angular_diff_signed(separation, target_deg) for separation in separations]
            for index in range(len(scan_times) - 1):
                left_ts = scan_times[index]
                right_ts = scan_times[index + 1]
                left_value = values[index]
                right_value = values[index + 1]
                if _crossed(left_value, right_value):
                    exact_ts = _interpolate_zero(left_ts, right_ts, left_value, right_value)
                    interval_days = max((right_ts - left_ts).total_seconds() / 86400.0, 1e-9)
                    relative_speed = (right_value - left_value) / interval_days
                    events.append(
                        AspectEvent(
                            exact_ts=exact_ts,
                            body_a=body_a,
                            body_b=body_b,
                            aspect_name=aspect_name,
                            aspect_deg=float(aspect_deg),
                            exact_delta_deg=0.0,
                            relative_speed_deg_day=relative_speed,
                            applying_before=abs(left_value) > abs(right_value),
                        )
                    )
    return _dedupe_aspect_events(sorted(events, key=lambda event: (event.exact_ts, event.body_a, event.body_b, event.aspect_name)))


def ordered_body_pair(body_a: str, body_b: str) -> tuple[str, str]:
    if body_a == body_b:
        raise ValueError("aspect pair bodies must be different.")
    return tuple(sorted((body_a.strip().title(), body_b.strip().title())))  # type: ignore[return-value]


def aspect_event_rows(events: list[AspectEvent], *, dataset_id: str, calc_version: str) -> list[dict]:
    return [
        {
            "exact_ts": event.exact_ts,
            "dataset_id": dataset_id,
            "event_id": _aspect_event_id(event),
            "body_a": event.body_a,
            "body_b": event.body_b,
            "aspect_name": event.aspect_name,
            "aspect_deg": event.aspect_deg,
            "exact_delta_deg": event.exact_delta_deg,
            "relative_speed_deg_day": event.relative_speed_deg_day,
            "applying_before": event.applying_before,
            "calc_version": calc_version,
            "source_note": "Exact major aspect refined from ecliptic longitude separation.",
        }
        for event in events
    ]


def aspect_event_windows(
    events: list[AspectEvent],
    *,
    dataset_id: str,
    calc_version: str,
    window_days_values: tuple[int, ...] = (3, 7, 14),
) -> list[dict]:
    rows = []
    for event in events:
        base_event_id = _aspect_event_id(event)
        for window_days in window_days_values:
            for rel_day in range(-window_days, window_days + 1):
                day = event.date + timedelta(days=rel_day)
                rows.append(
                    {
                        "ts": utc_midnight(day),
                        "dataset_id": dataset_id,
                        "event_id": f"{base_event_id}_pm{window_days}d",
                        "event_type": f"{event.body_a.lower()}_{event.body_b.lower()}_{event.aspect_name}",
                        "body": None,
                        "body_a": event.body_a,
                        "body_b": event.body_b,
                        "aspect_name": event.aspect_name,
                        "phase_name": None,
                        "exact_ts": event.exact_ts,
                        "exact_date_ts": utc_midnight(event.date),
                        "rel_day": rel_day,
                        "window_name": f"aspect_pm_{window_days}d",
                        "window_days": window_days,
                        "weight": 1.0,
                        "calc_version": calc_version,
                    }
                )
    return rows


def aspect_cluster_count(day, events: list[AspectEvent], window_days: int) -> int:
    return sum(1 for event in events if abs((event.date - day).days) <= window_days)


def _aspect_event_id(event: AspectEvent) -> str:
    return f"{event.body_a}_{event.body_b}_{event.aspect_name}_{event.exact_ts:%Y%m%d%H%M}"


def _aspect_delta(backend: EphemerisBackend, body_a: str, body_b: str, aspect_deg: float, ts: datetime) -> float:
    first = backend.get_position(body_a, ts)
    second = backend.get_position(body_b, ts)
    separation = normalize_360(second.lon_deg - first.lon_deg)
    return angular_diff_signed(separation, aspect_deg)


def _aspect_distance(separation: float, aspect_deg: float) -> float:
    if aspect_deg == 0:
        return min(abs(separation), abs(360.0 - separation))
    if aspect_deg == 180:
        return abs(abs(angular_diff_signed(separation, 0.0)) - 180.0)
    return min(angular_distance(separation, aspect_deg), angular_distance(separation, 360.0 - aspect_deg))


def _target_degrees(aspect_deg: float) -> tuple[float, ...]:
    if aspect_deg in {0.0, 180.0}:
        return (aspect_deg,)
    return (aspect_deg, 360.0 - aspect_deg)


def _scan_times(start_ts: datetime, end_ts: datetime, step: timedelta) -> list[datetime]:
    times = [start_ts]
    current = start_ts
    while current < end_ts:
        current = min(current + step, end_ts)
        times.append(current)
    return times


def _interpolate_zero(left_ts: datetime, right_ts: datetime, left_value: float, right_value: float) -> datetime:
    denominator = abs(left_value) + abs(right_value)
    fraction = 0.5 if denominator == 0 else abs(left_value) / denominator
    return left_ts + (right_ts - left_ts) * fraction


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


def _dedupe_aspect_events(events: list[AspectEvent]) -> list[AspectEvent]:
    seen = set()
    deduped = []
    for event in events:
        key = (event.body_a, event.body_b, event.aspect_name, event.exact_ts.strftime("%Y%m%d%H%M"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped
