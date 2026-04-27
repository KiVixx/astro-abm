from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

import requests


NASA_OMNI_LOW_RES_BASE_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni"


class NasaOmniClient:
    def __init__(self, base_url: str = NASA_OMNI_LOW_RES_BASE_URL, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_year(self, year: int) -> str:
        response = self.session.get(f"{self.base_url}/omni2_{year}.dat", timeout=60)
        response.raise_for_status()
        return response.text


def parse_omni2_hourly_payload(payload: str) -> list[dict[str, Any]]:
    rows = []
    for line in payload.splitlines():
        row = parse_omni2_hourly_line(line)
        if row:
            rows.append(row)
    return rows


def parse_omni2_hourly_line(line: str) -> dict[str, Any] | None:
    parts = line.split()
    if len(parts) < 39:
        return None

    year = int(parts[0])
    day_of_year = int(parts[1])
    hour = int(parts[2])
    ts = datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=day_of_year - 1, hours=hour)

    return {
        "ts": ts,
        "imf_bz": _omni_float(parts[16], fill_value=999.9),
        "solar_wind_speed": _omni_float(parts[24], fill_value=9999.0),
        "kp_index": _parse_omni_kp(parts[38]),
    }


def build_omni_space_weather_feature_rows(
    records: Iterable[dict[str, Any]],
    *,
    start_utc: datetime,
    end_utc: datetime,
    source: str = "nasa_omni",
) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        ts = record["ts"]
        if ts < start_utc or ts >= end_utc:
            continue
        rows.extend(
            _metric_rows(
                ts=ts,
                metrics=[
                    ("solar_wind_speed", record.get("solar_wind_speed")),
                    ("imf_bz", record.get("imf_bz")),
                    ("kp_index", record.get("kp_index")),
                ],
                source=source,
            )
        )
    return rows


def _metric_rows(*, ts: datetime, metrics: list[tuple[str, float | None]], source: str) -> list[dict[str, Any]]:
    rows = []
    for metric_name, metric_value in metrics:
        if metric_value is None:
            continue
        rows.append(
            {
                "ts": ts,
                "entity_type": "space_weather",
                "entity_id": "GLOBAL",
                "source": source,
                "interval": "1h",
                "asset_class": "macro",
                "market": None,
                "region": "GLOBAL",
                "metric_name": metric_name,
                "metric_value": metric_value,
                "observed_ts": ts,
                "available_ts": ts,
                "quality_flag": "authoritative",
                "notes": "cadence=3h; expanded_to=1h" if metric_name == "kp_index" else None,
            }
        )
    return rows


def _omni_float(value: str, *, fill_value: float) -> float | None:
    number = float(value)
    return None if number == fill_value else number


def _parse_omni_kp(value: str) -> float | None:
    code = int(value)
    if code == 99:
        return None
    base = code // 10
    suffix = code % 10
    if suffix == 0:
        return float(base)
    if suffix == 3:
        return base + (1.0 / 3.0)
    if suffix == 7:
        return base + (2.0 / 3.0)
    return code / 10.0
