from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from .marksix import _connect


SUPPORTED_BODIES = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
CURRENT_RULE_START = "2002-07-04"
MOTION_CONDITIONS = (
    "retrograde", "direct", "pre_station", "retrograde_entry",
    "retrograde_core", "retrograde_exit", "post_station",
)
MOON_PHASE_CONDITIONS = (
    "new_moon_zone", "first_quarter_zone", "full_moon_zone",
    "last_quarter_zone", "waxing_other", "waning_other",
)


@dataclass(frozen=True)
class _ObservedDraw:
    draw_id: str
    draw_date: str
    numbers: frozenset[int]
    extra_number: int
    is_retrograde: bool
    motion_phase: str


class SwissEphemerisBackend:
    """Small runtime-safe adapter; the research package is not installed with the API."""

    def __init__(self) -> None:
        import swisseph as swe

        self.swe = swe
        self.body_ids = {
            "Sun": swe.SUN, "Moon": swe.MOON,
            "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
            "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
        }

    def get_position(self, body: str, ts: datetime) -> Any:
        swe = self.swe
        jd_ut = swe.julday(ts.year, ts.month, ts.day, ts.hour + ts.minute / 60 + ts.second / 3600)
        values, _flags = swe.calc_ut(jd_ut, self.body_ids[body], swe.FLG_SWIEPH | swe.FLG_SPEED)
        return type("Position", (), {
            "lon_deg": float(values[0]) % 360,
            "lon_speed_deg_day": float(values[3]),
        })()


def _moon_phase_label(angle: float) -> str:
    angle %= 360
    if angle < 22.5 or angle >= 337.5:
        return "new_moon_zone"
    if 67.5 <= angle < 112.5:
        return "first_quarter_zone"
    if 157.5 <= angle < 202.5:
        return "full_moon_zone"
    if 247.5 <= angle < 292.5:
        return "last_quarter_zone"
    return "waxing_other" if angle < 180 else "waning_other"


def _two_proportion_p_value(success_a: int, total_a: int, success_b: int, total_b: int) -> float:
    if total_a == 0 or total_b == 0:
        return 1.0
    pooled = (success_a + success_b) / (total_a + total_b)
    variance = pooled * (1 - pooled) * (1 / total_a + 1 / total_b)
    if variance <= 0:
        return 1.0
    z = abs(success_a / total_a - success_b / total_b) / math.sqrt(variance)
    return math.erfc(z / math.sqrt(2))


def _bh_q_values(p_values: list[float]) -> list[float]:
    count = len(p_values)
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    result = [1.0] * count
    running = 1.0
    for rank_index in range(count - 1, -1, -1):
        original_index, value = ordered[rank_index]
        rank = rank_index + 1
        running = min(running, value * count / rank)
        result[original_index] = min(1.0, running)
    return result


def _motion_phase_calendar(
    *, body: str, start: date, end: date, backend: SwissEphemerisBackend,
    station_phase_days: int = 7, station_window_days: int = 14,
) -> dict[str, tuple[bool, str]]:
    scan_start = start - timedelta(days=station_window_days + 2)
    scan_end = end + timedelta(days=station_window_days + 2)
    speeds: list[tuple[date, bool]] = []
    cursor = scan_start
    while cursor <= scan_end:
        ts = datetime.combine(cursor, datetime.min.time(), tzinfo=UTC) + timedelta(hours=12)
        speeds.append((cursor, backend.get_position(body, ts).lon_speed_deg_day < 0))
        cursor += timedelta(days=1)
    stations: list[tuple[date, str]] = []
    for (previous_date, previous_retrograde), (current_date, current_retrograde) in zip(speeds, speeds[1:]):
        if previous_retrograde == current_retrograde:
            continue
        station_type = "direct_to_retrograde" if current_retrograde else "retrograde_to_direct"
        stations.append((current_date, station_type))

    calendar: dict[str, tuple[bool, str]] = {}
    for current_date, is_retrograde in speeds:
        previous_events = [(event_date, event_type) for event_date, event_type in stations if event_date <= current_date]
        next_events = [(event_date, event_type) for event_date, event_type in stations if event_date >= current_date]
        previous_station = previous_events[-1] if previous_events else None
        next_station = next_events[0] if next_events else None
        if is_retrograde:
            days_from_entry = (current_date - previous_station[0]).days if previous_station and previous_station[1] == "direct_to_retrograde" else 999
            days_to_exit = (next_station[0] - current_date).days if next_station and next_station[1] == "retrograde_to_direct" else 999
            if days_from_entry <= station_phase_days:
                phase = "retrograde_entry"
            elif days_to_exit <= station_phase_days:
                phase = "retrograde_exit"
            else:
                phase = "retrograde_core"
        else:
            days_to_entry = (next_station[0] - current_date).days if next_station and next_station[1] == "direct_to_retrograde" else 999
            days_from_exit = (current_date - previous_station[0]).days if previous_station and previous_station[1] == "retrograde_to_direct" else 999
            if 0 < days_to_entry <= station_window_days:
                phase = "pre_station"
            elif 0 <= days_from_exit <= station_window_days:
                phase = "post_station"
            else:
                phase = "direct"
        calendar[current_date.isoformat()] = (is_retrograde, phase)
    return calendar


def _load_draws(*, body: str, path: Path | None, start_date: str, end_date: str | None) -> list[_ObservedDraw]:
    backend = SwissEphemerisBackend()
    clauses = ["draw_date IS NOT NULL", "draw_date >= ?"]
    params: list[Any] = [start_date]
    if end_date:
        clauses.append("draw_date <= ?")
        params.append(end_date)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT draw_id, draw_date, ball_1, ball_2, ball_3, ball_4, ball_5, ball_6, extra_number "
            f"FROM marksix_draws WHERE {' AND '.join(clauses)} ORDER BY draw_date",
            params,
        ).fetchall()
    if not rows:
        return []
    calendar = _motion_phase_calendar(
        body=body, start=date.fromisoformat(rows[0]["draw_date"]),
        end=date.fromisoformat(rows[-1]["draw_date"]), backend=backend,
    )
    output: list[_ObservedDraw] = []
    for row in rows:
        is_retrograde, motion_phase = calendar[row["draw_date"]]
        output.append(_ObservedDraw(
            draw_id=row["draw_id"], draw_date=row["draw_date"],
            numbers=frozenset(int(row[f"ball_{index}"]) for index in range(1, 7)),
            extra_number=int(row["extra_number"]), is_retrograde=is_retrograde,
            motion_phase=motion_phase,
        ))
    return output


def _load_moon_phase_draws(*, path: Path | None, start_date: str, end_date: str | None) -> list[_ObservedDraw]:
    clauses = ["draw_date IS NOT NULL", "draw_date >= ?"]
    params: list[Any] = [start_date]
    if end_date:
        clauses.append("draw_date <= ?")
        params.append(end_date)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT draw_id, draw_date, ball_1, ball_2, ball_3, ball_4, ball_5, ball_6, extra_number "
            f"FROM marksix_draws WHERE {' AND '.join(clauses)} ORDER BY draw_date", params,
        ).fetchall()
    backend = SwissEphemerisBackend()
    output: list[_ObservedDraw] = []
    for row in rows:
        timestamp = datetime.fromisoformat(f"{row['draw_date']}T12:00:00+00:00").astimezone(UTC)
        moon = backend.get_position("Moon", timestamp)
        sun = backend.get_position("Sun", timestamp)
        phase = _moon_phase_label(moon.lon_deg - sun.lon_deg)
        output.append(_ObservedDraw(
            draw_id=row["draw_id"], draw_date=row["draw_date"],
            numbers=frozenset(int(row[f"ball_{index}"]) for index in range(1, 7)),
            extra_number=int(row["extra_number"]), is_retrograde=False, motion_phase=phase,
        ))
    return output


def _number_statistics(
    *, selected: list[_ObservedDraw], baseline: list[_ObservedDraw], number_role: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    p_values: list[float] = []
    for number in range(1, 50):
        selected_hits = sum(number in draw.numbers if number_role == "main" else number == draw.extra_number for draw in selected)
        baseline_hits = sum(number in draw.numbers if number_role == "main" else number == draw.extra_number for draw in baseline)
        selected_rate = selected_hits / len(selected) if selected else 0.0
        baseline_rate = baseline_hits / len(baseline) if baseline else 0.0
        p_value = _two_proportion_p_value(selected_hits, len(selected), baseline_hits, len(baseline))
        p_values.append(p_value)
        rows.append({
            "number": number, "condition_hits": selected_hits, "condition_rate": selected_rate,
            "baseline_hits": baseline_hits, "baseline_rate": baseline_rate,
            "rate_difference": selected_rate - baseline_rate,
            "lift": selected_rate / baseline_rate if baseline_rate else None, "p_value": p_value,
        })
    for row, q_value in zip(rows, _bh_q_values(p_values), strict=True):
        row["q_value_fdr"] = q_value
    return rows


def analyze_retrograde_numbers(
    *, body: str = "Mercury", condition: str = "retrograde",
    number_role: Literal["main", "extra"] = "main", start_date: str = CURRENT_RULE_START,
    end_date: str | None = None, path: Path | None = None,
) -> dict[str, Any]:
    body = body.strip().title()
    if body not in SUPPORTED_BODIES:
        raise ValueError(f"Unsupported retrograde body: {body}")
    if condition not in MOTION_CONDITIONS:
        raise ValueError(f"Unsupported motion condition: {condition}")
    draws = _load_draws(body=body, path=path, start_date=start_date, end_date=end_date)
    if condition == "retrograde":
        selected = [draw for draw in draws if draw.is_retrograde]
    elif condition == "direct":
        selected = [draw for draw in draws if not draw.is_retrograde]
    else:
        selected = [draw for draw in draws if draw.motion_phase == condition]
    baseline = [draw for draw in draws if draw not in selected]
    rows = _number_statistics(selected=selected, baseline=baseline, number_role=number_role)
    return {
        "context_type": "planet_motion", "body": body, "condition": condition, "number_role": number_role,
        "start_date": start_date, "end_date": end_date or (draws[-1].draw_date if draws else None),
        "rule_era": "current_6_of_49", "total_draws": len(draws),
        "condition_draws": len(selected), "baseline_draws": len(baseline), "numbers": rows,
        "method_notes": [
            "Only dated draws in the current 6/49 era are included by default.",
            "Motion phase is derived from geocentric tropical longitude speed sampled daily at 12:00 UTC.",
            "Station entry/exit phases use seven days; pre/post station research windows use fourteen days.",
            "Lift and p/q values are exploratory historical associations; they do not change future draw probability.",
            "Main and extra numbers are analyzed separately, with Benjamini-Hochberg FDR across 49 numbers.",
        ],
    }


def analyze_moon_phase_numbers(
    *, condition: str = "full_moon_zone", number_role: Literal["main", "extra"] = "main",
    start_date: str = CURRENT_RULE_START, end_date: str | None = None, path: Path | None = None,
) -> dict[str, Any]:
    if condition not in MOON_PHASE_CONDITIONS:
        raise ValueError(f"Unsupported moon phase condition: {condition}")
    draws = _load_moon_phase_draws(path=path, start_date=start_date, end_date=end_date)
    selected = [draw for draw in draws if draw.motion_phase == condition]
    baseline = [draw for draw in draws if draw.motion_phase != condition]
    return {
        "context_type": "moon_phase", "body": "Moon", "condition": condition,
        "number_role": number_role, "start_date": start_date,
        "end_date": end_date or (draws[-1].draw_date if draws else None),
        "rule_era": "current_6_of_49", "total_draws": len(draws),
        "condition_draws": len(selected), "baseline_draws": len(baseline),
        "numbers": _number_statistics(selected=selected, baseline=baseline, number_role=number_role),
        "method_notes": [
            "Moon phase is the geocentric tropical Moon-Sun elongation sampled at 12:00 UTC on each draw date.",
            "The four named phase zones are +/-22.5 degrees around 0, 90, 180, and 270 degrees; they are daily zones, not exact event timestamps.",
            "Lift and p/q values are exploratory historical associations and do not change future draw probability.",
        ],
    }
