from __future__ import annotations

from datetime import UTC
from typing import Any

from .ephemeris_backend import PositionRecord
from .positions import zodiac_degree, zodiac_sign


POSITION_COLUMNS = [
    "ts",
    "dataset_id",
    "body",
    "lon_deg",
    "lat_deg",
    "distance_au",
    "lon_speed_deg_day",
    "lat_speed_deg_day",
    "distance_speed_au_day",
    "right_ascension_deg",
    "declination_deg",
    "zodiac_sign",
    "zodiac_degree",
    "is_retrograde",
    "is_oob",
    "ephemeris_backend",
    "calc_version",
    "source_note",
]


def position_to_row(
    record: PositionRecord,
    *,
    dataset_id: str,
    calc_version: str,
    oob_threshold_deg: float,
    source_note: str = "Swiss Ephemeris geocentric daily sample at 00:00 UTC.",
) -> dict[str, Any]:
    declination = record.declination_deg
    return {
        "ts": record.ts.astimezone(UTC),
        "dataset_id": dataset_id,
        "body": record.body,
        "lon_deg": record.lon_deg,
        "lat_deg": record.lat_deg,
        "distance_au": record.distance_au,
        "lon_speed_deg_day": record.lon_speed_deg_day,
        "lat_speed_deg_day": record.lat_speed_deg_day,
        "distance_speed_au_day": record.distance_speed_au_day,
        "right_ascension_deg": record.right_ascension_deg,
        "declination_deg": declination,
        "zodiac_sign": zodiac_sign(record.lon_deg),
        "zodiac_degree": zodiac_degree(record.lon_deg),
        "is_retrograde": record.lon_speed_deg_day < 0.0,
        "is_oob": abs(declination) > oob_threshold_deg if declination is not None else None,
        "ephemeris_backend": "swiss_ephemeris",
        "calc_version": calc_version,
        "source_note": source_note,
    }


def feature_rows_to_facts(features: list[dict[str, Any]], *, dataset_id: str, calc_version: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    skip = {"ts", "dataset_id", "calc_version"}
    for row in features:
        ts = row["ts"]
        for key, value in row.items():
            if key in skip or value is None:
                continue
            body, metric = _split_body_metric(key)
            fact = {
                "ts": ts,
                "dataset_id": dataset_id,
                "body": body,
                "metric": metric,
                "metric_group": _metric_group(metric),
                "value_double": None,
                "value_long": None,
                "value_bool": None,
                "value_symbol": None,
                "value_text": None,
                "unit": None,
                "ephemeris_backend": "swiss_ephemeris",
                "calc_version": calc_version,
                "source_note": "Derived from astro_daily_features.",
            }
            if isinstance(value, bool):
                fact["value_bool"] = value
            elif isinstance(value, int):
                fact["value_long"] = value
            elif isinstance(value, float):
                fact["value_double"] = value
            elif isinstance(value, str) and len(value) < 128:
                fact["value_symbol"] = value
            else:
                fact["value_text"] = str(value)
            facts.append(fact)
    return facts


def _split_body_metric(key: str) -> tuple[str, str]:
    for body in ("mercury", "venus", "mars", "jupiter", "saturn"):
        prefix = f"{body}_"
        if key.startswith(prefix):
            return body.capitalize(), key[len(prefix) :]
    if key.startswith("moon_"):
        return "Moon", key[len("moon_") :]
    return "ALL", key


def _metric_group(metric: str) -> str:
    if "phase" in metric:
        return "phase"
    if "station" in metric:
        return "station"
    if "retrograde" in metric:
        return "retrograde"
    if "aspect" in metric or "saturn_angle" in metric:
        return "aspect"
    if "moon" in metric or "illumination" in metric:
        return "moon_phase"
    return "derived"
