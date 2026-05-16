from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .angle_math import normalize_360
from .ephemeris_backend import EphemerisBackend, PositionRecord


class SwissEphemerisBackend(EphemerisBackend):
    def __init__(self, swe: Any | None = None):
        if swe is None:
            import swisseph as swe_module

            swe = swe_module
        self.swe = swe
        self.body_ids = {
            "Sun": self.swe.SUN,
            "Moon": self.swe.MOON,
            "Mercury": self.swe.MERCURY,
            "Venus": self.swe.VENUS,
            "Mars": self.swe.MARS,
            "Jupiter": self.swe.JUPITER,
            "Saturn": self.swe.SATURN,
            "Uranus": self.swe.URANUS,
            "Neptune": self.swe.NEPTUNE,
            "Pluto": self.swe.PLUTO,
        }
        self._position_cache: dict[tuple[str, int], PositionRecord] = {}

    def get_position(self, body: str, ts: datetime) -> PositionRecord:
        body = body.strip().title()
        if body not in self.body_ids:
            raise ValueError(f"Unsupported body: {body}")
        ts_utc = ts.astimezone(UTC)
        cache_key = (body, int(ts_utc.timestamp()))
        cached = self._position_cache.get(cache_key)
        if cached is not None:
            return cached
        jd_ut = self._to_jd_ut(ts_utc)
        flags = self.swe.FLG_SWIEPH | self.swe.FLG_SPEED
        equatorial_flags = flags | getattr(self.swe, "FLG_EQUATORIAL", 0)
        xx, _ = self.swe.calc_ut(jd_ut, self.body_ids[body], flags)
        equatorial_xx, _ = self.swe.calc_ut(jd_ut, self.body_ids[body], equatorial_flags)
        record = PositionRecord(
            ts=ts_utc,
            body=body,
            lon_deg=normalize_360(float(xx[0])),
            lat_deg=float(xx[1]),
            distance_au=float(xx[2]),
            lon_speed_deg_day=float(xx[3]),
            lat_speed_deg_day=float(xx[4]) if len(xx) > 4 else None,
            distance_speed_au_day=float(xx[5]) if len(xx) > 5 else None,
            right_ascension_deg=float(equatorial_xx[0]) if len(equatorial_xx) > 0 else None,
            declination_deg=float(equatorial_xx[1]) if len(equatorial_xx) > 1 else None,
        )
        self._position_cache[cache_key] = record
        return record

    def _to_jd_ut(self, ts: datetime) -> float:
        ts_utc = ts.astimezone(UTC)
        seconds = ts_utc.second + ts_utc.microsecond / 1_000_000
        _jd_et, jd_ut = self.swe.utc_to_jd(
            ts_utc.year,
            ts_utc.month,
            ts_utc.day,
            ts_utc.hour,
            ts_utc.minute,
            seconds,
            self.swe.GREG_CAL,
        )
        return jd_ut
