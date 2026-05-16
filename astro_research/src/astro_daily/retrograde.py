from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Iterable

from .calendar import utc_midnight
from .ephemeris_backend import EphemerisBackend


STATION_IN = "direct_to_retrograde"
STATION_OUT = "retrograde_to_direct"
ACTIVE_RETROGRADE_PHASES = {"retrograde_entry", "retrograde_core", "retrograde_exit"}


@dataclass(frozen=True)
class StationEvent:
    exact_ts: datetime
    body: str
    station_type: str

    @property
    def date(self) -> date:
        return self.exact_ts.astimezone(UTC).date()


@dataclass(frozen=True)
class RetrogradeCycle:
    cycle_id: str
    body: str
    station_in_ts: datetime
    station_out_ts: datetime
    station_phase_days: int
    pre_post_window_days: int

    @property
    def station_in_date(self) -> date:
        return self.station_in_ts.astimezone(UTC).date()

    @property
    def station_out_date(self) -> date:
        return self.station_out_ts.astimezone(UTC).date()

    @property
    def retrograde_days(self) -> int:
        return (self.station_out_date - self.station_in_date).days + 1

    @property
    def pre_window_start_date(self) -> date:
        return self.station_in_date - timedelta(days=self.pre_post_window_days)

    @property
    def post_window_end_date(self) -> date:
        return self.station_out_date + timedelta(days=self.pre_post_window_days)


@dataclass(frozen=True)
class DailyRetrogradeState:
    body: str
    phase: str
    is_retrograde: bool
    days_since_station: int | None
    days_until_station: int | None
    cycle_id: str | None


def scan_station_events(
    *,
    backend: EphemerisBackend,
    bodies: Iterable[str],
    start_ts: datetime,
    end_ts: datetime,
    step_hours: int = 6,
    tolerance_seconds: int = 60,
) -> list[StationEvent]:
    events: list[StationEvent] = []
    step = timedelta(hours=step_hours)
    for body in bodies:
        left_ts = start_ts
        left_speed = backend.get_speed(body, left_ts)
        while left_ts < end_ts:
            right_ts = min(left_ts + step, end_ts)
            right_speed = backend.get_speed(body, right_ts)
            if _sign_changed(left_speed, right_speed):
                exact_ts = _refine_speed_zero(
                    backend=backend,
                    body=body,
                    left_ts=left_ts,
                    right_ts=right_ts,
                    left_speed=left_speed,
                    right_speed=right_speed,
                    tolerance_seconds=tolerance_seconds,
                )
                before = backend.get_speed(body, exact_ts - timedelta(hours=1))
                after = backend.get_speed(body, exact_ts + timedelta(hours=1))
                if before > 0 and after < 0:
                    events.append(StationEvent(exact_ts=exact_ts, body=body, station_type=STATION_IN))
                elif before < 0 and after > 0:
                    events.append(StationEvent(exact_ts=exact_ts, body=body, station_type=STATION_OUT))
            left_ts = right_ts
            left_speed = right_speed
    return sorted(events, key=lambda event: (event.body, event.exact_ts))


def pair_retrograde_cycles(
    station_events: Iterable[StationEvent],
    *,
    station_phase_days: int,
    pre_post_window_days: int,
) -> list[RetrogradeCycle]:
    cycles: list[RetrogradeCycle] = []
    for body in sorted({event.body for event in station_events}):
        pending_in: StationEvent | None = None
        for event in sorted((item for item in station_events if item.body == body), key=lambda item: item.exact_ts):
            if event.station_type == STATION_IN:
                pending_in = event
            elif event.station_type == STATION_OUT and pending_in is not None and pending_in.exact_ts < event.exact_ts:
                cycles.append(
                    RetrogradeCycle(
                        cycle_id=f"{body}_{pending_in.date:%Y%m%d}_{event.date:%Y%m%d}",
                        body=body,
                        station_in_ts=pending_in.exact_ts,
                        station_out_ts=event.exact_ts,
                        station_phase_days=station_phase_days,
                        pre_post_window_days=pre_post_window_days,
                    )
                )
                pending_in = None
    return cycles


def daily_retrograde_state(day: date, body: str, cycles: Iterable[RetrogradeCycle], station_events: Iterable[StationEvent]) -> DailyRetrogradeState:
    body_cycles = [cycle for cycle in cycles if cycle.body == body]
    phase = "direct"
    cycle_id = None
    for cycle in body_cycles:
        if cycle.pre_window_start_date <= day < cycle.station_in_date:
            phase = "pre_station"
            cycle_id = cycle.cycle_id
        if cycle.station_out_date < day <= cycle.post_window_end_date:
            phase = "post_station"
            cycle_id = cycle.cycle_id
        if cycle.station_in_date <= day <= cycle.station_in_date + timedelta(days=cycle.station_phase_days):
            phase = "retrograde_entry"
            cycle_id = cycle.cycle_id
        if cycle.station_out_date - timedelta(days=cycle.station_phase_days) <= day <= cycle.station_out_date:
            phase = "retrograde_exit"
            cycle_id = cycle.cycle_id
        core_start = cycle.station_in_date + timedelta(days=cycle.station_phase_days + 1)
        core_end = cycle.station_out_date - timedelta(days=cycle.station_phase_days + 1)
        if core_start <= day <= core_end:
            phase = "retrograde_core"
            cycle_id = cycle.cycle_id
        if phase != "direct" and cycle_id == cycle.cycle_id:
            break

    body_station_dates = sorted(event.date for event in station_events if event.body == body)
    previous_dates = [station_date for station_date in body_station_dates if station_date <= day]
    future_dates = [station_date for station_date in body_station_dates if station_date >= day]
    days_since = (day - previous_dates[-1]).days if previous_dates else None
    days_until = (future_dates[0] - day).days if future_dates else None
    return DailyRetrogradeState(
        body=body,
        phase=phase,
        is_retrograde=phase in ACTIVE_RETROGRADE_PHASES,
        days_since_station=days_since,
        days_until_station=days_until,
        cycle_id=cycle_id,
    )


def station_cluster_count(day: date, station_events: Iterable[StationEvent], window_days: int) -> int:
    return sum(1 for event in station_events if abs((event.date - day).days) <= window_days)


def build_station_event_windows(
    station_events: Iterable[StationEvent],
    *,
    dataset_id: str,
    calc_version: str,
    window_days_values: Iterable[int] = (7, 14, 30),
) -> list[dict]:
    rows: list[dict] = []
    for event in station_events:
        base_event_id = f"{event.body}_{event.station_type}_{event.exact_ts:%Y%m%d%H%M}"
        for window_days in window_days_values:
            for rel_day in range(-window_days, window_days + 1):
                day = event.date + timedelta(days=rel_day)
                rows.append(
                    {
                        "ts": utc_midnight(day),
                        "dataset_id": dataset_id,
                        "event_id": f"{base_event_id}_pm{window_days}d",
                        "event_type": f"{event.body.lower()}_{event.station_type}",
                        "body": event.body,
                        "body_a": None,
                        "body_b": None,
                        "aspect_name": None,
                        "phase_name": None,
                        "exact_ts": event.exact_ts,
                        "exact_date_ts": utc_midnight(event.date),
                        "rel_day": rel_day,
                        "window_name": f"station_pm_{window_days}d",
                        "window_days": window_days,
                        "weight": 1.0,
                        "calc_version": calc_version,
                    }
                )
    return rows


def _sign_changed(first: float, second: float) -> bool:
    return first == 0.0 or second == 0.0 or (first < 0.0 < second) or (second < 0.0 < first)


def _refine_speed_zero(
    *,
    backend: EphemerisBackend,
    body: str,
    left_ts: datetime,
    right_ts: datetime,
    left_speed: float,
    right_speed: float,
    tolerance_seconds: int,
) -> datetime:
    left = left_ts
    right = right_ts
    left_value = left_speed
    right_value = right_speed
    while (right - left).total_seconds() > tolerance_seconds:
        mid = left + (right - left) / 2
        mid_value = backend.get_speed(body, mid)
        if _sign_changed(left_value, mid_value):
            right = mid
            right_value = mid_value
        else:
            left = mid
            left_value = mid_value
    return left + (right - left) / 2
