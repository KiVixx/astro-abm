from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .ephemeris_backend import EphemerisBackend, PositionRecord

ZODIAC_SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)


def build_daily_positions(*, backend: EphemerisBackend, bodies: Iterable[str], timestamps: Iterable[datetime]) -> list[PositionRecord]:
    return [backend.get_position(body, ts) for ts in timestamps for body in bodies]


def zodiac_sign(lon_deg: float) -> str:
    return ZODIAC_SIGNS[int(lon_deg // 30) % 12]


def zodiac_degree(lon_deg: float) -> float:
    return lon_deg % 30.0
