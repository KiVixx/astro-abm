from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PositionRecord:
    ts: datetime
    body: str
    lon_deg: float
    lat_deg: float
    distance_au: float
    lon_speed_deg_day: float
    lat_speed_deg_day: float | None
    distance_speed_au_day: float | None
    right_ascension_deg: float | None
    declination_deg: float | None


class EphemerisBackend(ABC):
    @abstractmethod
    def get_position(self, body: str, ts: datetime) -> PositionRecord:
        raise NotImplementedError

    def get_speed(self, body: str, ts: datetime) -> float:
        return self.get_position(body, ts).lon_speed_deg_day
