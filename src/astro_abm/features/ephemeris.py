from __future__ import annotations

import math
from functools import lru_cache
from datetime import UTC, datetime
from typing import Any


ANGLE_PAIRS = (
    ("sun", "moon"),
    ("sun", "mercury"),
    ("sun", "venus"),
    ("mars", "saturn"),
    ("jupiter", "saturn"),
)
ASPECT_DEGREES = (0, 60, 90, 120, 180)
RETROGRADE_BODIES = ("mercury", "venus", "mars", "jupiter", "saturn")
DECLINATION_BODIES = ("moon", "mercury", "venus", "mars", "jupiter", "saturn")
OOB_DECLINATION_DEGREES = 23.4367


EPHEMERIS_FEATURE_METRICS = (
    "moon_phase_pct",
    "moon_is_waxing",
    *(
        metric
        for first, second in ANGLE_PAIRS
        for pair in (f"{first}_{second}",)
        for metric in (
            f"{pair}_angle_abs",
            f"{pair}_angle_signed",
            f"{pair}_angle_sin",
            f"{pair}_angle_cos",
            *(f"{pair}_aspect_strength_{aspect}" for aspect in ASPECT_DEGREES),
        )
    ),
    *(
        metric
        for body in RETROGRADE_BODIES
        for metric in (
            f"{body}_lon_speed",
            f"{body}_is_retrograde",
            f"{body}_speed_abs",
            f"{body}_speed_zscore",
            f"{body}_abs_speed_percentile",
            f"{body}_days_since_station",
            f"{body}_days_until_station",
            f"{body}_days_to_station_nearest",
        )
    ),
    *(
        metric
        for body in DECLINATION_BODIES
        for metric in (
            f"{body}_declination",
            f"{body}_declination_abs",
            f"{body}_is_oob",
        )
    ),
)


class EphemerisCalculator:
    def __init__(self, swe: Any | None = None, *, aspect_sigma_degrees: float = 6.0):
        if swe is None:
            import swisseph as swe_module

            swe = swe_module
        self.swe = swe
        self.aspect_sigma_degrees = aspect_sigma_degrees
        self.planets = {
            "sun": self.swe.SUN,
            "moon": self.swe.MOON,
            "mercury": self.swe.MERCURY,
            "venus": self.swe.VENUS,
            "mars": self.swe.MARS,
            "jupiter": self.swe.JUPITER,
            "saturn": self.swe.SATURN,
        }

    def compute_features(self, dt: datetime) -> dict[str, float | bool | None]:
        jd_ut = self._to_jd_ut(dt)
        flags = self.swe.FLG_SWIEPH | self.swe.FLG_SPEED
        equatorial_flags = flags | getattr(self.swe, "FLG_EQUATORIAL", 0)
        positions = {}
        for name, body in self.planets.items():
            xx, _ = self.swe.calc_ut(jd_ut, body, flags)
            equatorial_xx, _ = self.swe.calc_ut(jd_ut, body, equatorial_flags)
            positions[name] = {
                "lon": self.swe.degnorm(xx[0]),
                "lat": xx[1],
                "dist": xx[2],
                "speed_lon": xx[3],
                "declination": equatorial_xx[1],
            }

        sun_lon = positions["sun"]["lon"]
        moon_lon = positions["moon"]["lon"]
        elongation = self.swe.degnorm(moon_lon - sun_lon)
        moon_phase_pct = (1 - math.cos(math.radians(elongation))) / 2 * 100.0
        features: dict[str, float | bool] = {
            "moon_phase_pct": moon_phase_pct,
            "moon_is_waxing": elongation < 180.0,
        }

        for first, second in ANGLE_PAIRS:
            pair = f"{first}_{second}"
            signed_angle = float(self.swe.difdeg2n(positions[second]["lon"], positions[first]["lon"]))
            abs_angle = abs(signed_angle)
            features.update(
                {
                    f"{pair}_angle_abs": abs_angle,
                    f"{pair}_angle_signed": signed_angle,
                    f"{pair}_angle_sin": math.sin(math.radians(signed_angle)),
                    f"{pair}_angle_cos": math.cos(math.radians(signed_angle)),
                }
            )
            for aspect in ASPECT_DEGREES:
                features[f"{pair}_aspect_strength_{aspect}"] = _aspect_strength(
                    abs_angle,
                    aspect_degrees=aspect,
                    sigma_degrees=self.aspect_sigma_degrees,
                )

        for body_name in RETROGRADE_BODIES:
            body = self.planets[body_name]
            speed = float(positions[body_name]["speed_lon"])
            speed_context = self._speed_context(body, _jd_day(jd_ut))
            features.update(
                {
                    f"{body_name}_lon_speed": speed,
                    f"{body_name}_is_retrograde": speed < 0.0,
                    f"{body_name}_speed_abs": abs(speed),
                    f"{body_name}_speed_zscore": speed_context["speed_zscore"],
                    f"{body_name}_abs_speed_percentile": speed_context["abs_speed_percentile"],
                    f"{body_name}_days_since_station": speed_context["days_since_station"],
                    f"{body_name}_days_until_station": speed_context["days_until_station"],
                    f"{body_name}_days_to_station_nearest": speed_context["days_to_station_nearest"],
                }
            )

        for body_name in DECLINATION_BODIES:
            declination = float(positions[body_name]["declination"])
            features.update(
                {
                    f"{body_name}_declination": declination,
                    f"{body_name}_declination_abs": abs(declination),
                    f"{body_name}_is_oob": abs(declination) > OOB_DECLINATION_DEGREES,
                }
            )

        return features

    @lru_cache(maxsize=20_000)
    def _speed_context(self, body: int, jd_day: int) -> dict[str, float | None]:
        samples = [self._longitude_speed(body, jd_day + offset) for offset in range(-90, 91, 3)]
        current_speed = self._longitude_speed(body, jd_day)
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / max(1, len(samples) - 1)
        std = math.sqrt(variance)
        abs_samples = sorted(abs(value) for value in samples)
        abs_speed = abs(current_speed)
        percentile = sum(1 for value in abs_samples if value <= abs_speed) / len(abs_samples)
        days_since, days_until = self._station_distances(body, jd_day)
        nearest_candidates = [abs(value) for value in (days_since, days_until) if value is not None]
        return {
            "speed_zscore": (current_speed - mean) / std if std > 0 else 0.0,
            "abs_speed_percentile": percentile,
            "days_since_station": days_since,
            "days_until_station": days_until,
            "days_to_station_nearest": min(nearest_candidates) if nearest_candidates else None,
        }

    def _station_distances(self, body: int, jd_day: int, *, max_days: int = 370) -> tuple[float | None, float | None]:
        current_speed = self._longitude_speed(body, jd_day)
        days_since = None
        previous_speed = current_speed
        for days in range(1, max_days + 1):
            speed = self._longitude_speed(body, jd_day - days)
            if _sign_changed(previous_speed, speed):
                days_since = float(days)
                break
            previous_speed = speed

        days_until = None
        previous_speed = current_speed
        for days in range(1, max_days + 1):
            speed = self._longitude_speed(body, jd_day + days)
            if _sign_changed(previous_speed, speed):
                days_until = float(days)
                break
            previous_speed = speed
        return days_since, days_until

    def _longitude_speed(self, body: int, jd_ut: float) -> float:
        xx, _ = self.swe.calc_ut(jd_ut, body, self.swe.FLG_SWIEPH | self.swe.FLG_SPEED)
        return float(xx[3])

    def _to_jd_ut(self, dt: datetime) -> float:
        dt_utc = dt.astimezone(UTC)
        seconds = dt_utc.second + (dt_utc.microsecond / 1_000_000)
        _jd_et, jd_ut = self.swe.utc_to_jd(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            dt_utc.hour,
            dt_utc.minute,
            seconds,
            self.swe.GREG_CAL,
        )
        return jd_ut


def build_ephemeris_feature_rows(*, ts: datetime, features: dict[str, float | bool | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric_name, raw_value in features.items():
        if raw_value is None:
            continue
        metric_value = 1.0 if raw_value is True else 0.0 if raw_value is False else float(raw_value)
        rows.append(
            {
                "ts": ts,
                "entity_type": "ephemeris",
                "entity_id": "GLOBAL",
                "source": "pyswisseph",
                "interval": "1h",
                "asset_class": "macro",
                "market": None,
                "region": "GLOBAL",
                "metric_name": metric_name,
                "metric_value": metric_value,
                "observed_ts": ts,
                "available_ts": ts,
                "quality_flag": "deterministic",
            }
        )
    return rows


def _aspect_strength(abs_angle: float, *, aspect_degrees: int, sigma_degrees: float) -> float:
    distance = abs(abs_angle - aspect_degrees)
    return math.exp(-(distance**2) / (2 * sigma_degrees**2))


def _sign_changed(first: float, second: float) -> bool:
    return first == 0.0 or second == 0.0 or (first < 0.0 < second) or (second < 0.0 < first)


def _jd_day(jd_ut: float) -> int:
    return int(math.floor(jd_ut))
