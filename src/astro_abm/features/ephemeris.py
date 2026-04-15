from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any


class EphemerisCalculator:
    def __init__(self, swe: Any | None = None):
        if swe is None:
            import swisseph as swe_module

            swe = swe_module
        self.swe = swe
        self.planets = {
            "sun": self.swe.SUN,
            "moon": self.swe.MOON,
            "mercury": self.swe.MERCURY,
            "venus": self.swe.VENUS,
            "mars": self.swe.MARS,
            "jupiter": self.swe.JUPITER,
            "saturn": self.swe.SATURN,
        }

    def compute_features(self, dt: datetime) -> dict[str, float | bool]:
        jd_ut = self._to_jd_ut(dt)
        flags = self.swe.FLG_SWIEPH | self.swe.FLG_SPEED
        positions = {}
        for name, body in self.planets.items():
            xx, _ = self.swe.calc_ut(jd_ut, body, flags)
            positions[name] = {
                "lon": self.swe.degnorm(xx[0]),
                "lat": xx[1],
                "dist": xx[2],
                "speed_lon": xx[3],
            }

        sun_lon = positions["sun"]["lon"]
        moon_lon = positions["moon"]["lon"]
        elongation = self.swe.degnorm(moon_lon - sun_lon)
        moon_phase_pct = (1 - math.cos(math.radians(elongation))) / 2 * 100.0
        sun_moon_angle_signed = float(self.swe.difdeg2n(moon_lon, sun_lon))
        mars_jupiter_angle_signed = float(self.swe.difdeg2n(positions["mars"]["lon"], positions["jupiter"]["lon"]))

        return {
            "moon_phase_pct": moon_phase_pct,
            "moon_is_waxing": elongation < 180.0,
            "sun_moon_angle_abs": abs(sun_moon_angle_signed),
            "sun_moon_angle_signed": sun_moon_angle_signed,
            "mars_jupiter_angle_abs": abs(mars_jupiter_angle_signed),
            "mars_jupiter_angle_signed": mars_jupiter_angle_signed,
        }

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


def build_ephemeris_feature_rows(*, ts: datetime, features: dict[str, float | bool]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric_name, raw_value in features.items():
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
                "quality_flag": "derived",
            }
        )
    return rows
