from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .marksix import _connect


SUPPORTED_BODIES = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
CURRENT_RULE_START = "2002-07-04"


@dataclass(frozen=True)
class _ObservedDraw:
    draw_id: str
    draw_date: str
    numbers: frozenset[int]
    extra_number: int
    is_retrograde: bool


class SwissEphemerisBackend:
    """Small runtime-safe adapter; the research package is not installed with the API."""

    def __init__(self) -> None:
        import swisseph as swe

        self.swe = swe
        self.body_ids = {
            "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
            "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
        }

    def get_position(self, body: str, ts: datetime) -> Any:
        swe = self.swe
        jd_ut = swe.julday(ts.year, ts.month, ts.day, ts.hour + ts.minute / 60 + ts.second / 3600)
        values, _flags = swe.calc_ut(jd_ut, self.body_ids[body], swe.FLG_SWIEPH | swe.FLG_SPEED)
        return type("Position", (), {"lon_speed_deg_day": float(values[3])})()


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
    output: list[_ObservedDraw] = []
    for row in rows:
        timestamp = datetime.fromisoformat(f"{row['draw_date']}T12:00:00+00:00").astimezone(UTC)
        speed = backend.get_position(body, timestamp).lon_speed_deg_day
        output.append(_ObservedDraw(
            draw_id=row["draw_id"], draw_date=row["draw_date"],
            numbers=frozenset(int(row[f"ball_{index}"]) for index in range(1, 7)),
            extra_number=int(row["extra_number"]), is_retrograde=speed < 0,
        ))
    return output


def analyze_retrograde_numbers(
    *, body: str = "Mercury", condition: Literal["retrograde", "direct"] = "retrograde",
    number_role: Literal["main", "extra"] = "main", start_date: str = CURRENT_RULE_START,
    end_date: str | None = None, path: Path | None = None,
) -> dict[str, Any]:
    body = body.strip().title()
    if body not in SUPPORTED_BODIES:
        raise ValueError(f"Unsupported retrograde body: {body}")
    draws = _load_draws(body=body, path=path, start_date=start_date, end_date=end_date)
    selected = [draw for draw in draws if draw.is_retrograde == (condition == "retrograde")]
    baseline = [draw for draw in draws if draw not in selected]
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
            "lift": selected_rate / baseline_rate if baseline_rate else None,
            "p_value": p_value,
        })
    for row, q_value in zip(rows, _bh_q_values(p_values), strict=True):
        row["q_value_fdr"] = q_value
    return {
        "body": body, "condition": condition, "number_role": number_role,
        "start_date": start_date, "end_date": end_date or (draws[-1].draw_date if draws else None),
        "rule_era": "current_6_of_49", "total_draws": len(draws),
        "condition_draws": len(selected), "baseline_draws": len(baseline), "numbers": rows,
        "method_notes": [
            "Only dated draws in the current 6/49 era are included by default.",
            "Retrograde is determined from geocentric tropical longitude speed at 12:00 UTC on each draw date.",
            "Lift and p/q values are exploratory historical associations; they do not change future draw probability.",
            "Main and extra numbers are analyzed separately, with Benjamini-Hochberg FDR across 49 numbers.",
        ],
    }
