from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import requests

NOAA_SPACE_WEATHER_ENDPOINTS = {
    "plasma": "https://services.swpc.noaa.gov/products/solar-wind/plasma-1-day.json",
    "mag": "https://services.swpc.noaa.gov/products/solar-wind/mag-1-day.json",
    "xray": "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json",
    "kp": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
}


def _parse_noaa_time(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    if "T" in value:
        return datetime.fromisoformat(value).astimezone(UTC)
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=UTC)


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, str):
        try:
            if value.strip() == "":
                return None
            return float(value)
        except ValueError:
            return value
    return value


def parse_noaa_table_feed(payload: list[list[Any]]) -> list[dict[str, Any]]:
    if not payload:
        return []
    header = payload[0]
    rows: list[dict[str, Any]] = []
    for raw_row in payload[1:]:
        item = {key: _coerce_scalar(value) for key, value in zip(header, raw_row)}
        if "time_tag" in item and isinstance(item["time_tag"], str):
            item["time_tag"] = _parse_noaa_time(item["time_tag"])
        rows.append(item)
    return rows


def parse_xray_flux_feed(payload: list[dict[str, Any]], energy_channel: str = "0.1-0.8nm") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        if item.get("energy") != energy_channel:
            continue
        rows.append(
            {
                "time_tag": _parse_noaa_time(item["time_tag"]),
                "energy": item["energy"],
                "flux": float(item["flux"]),
            }
        )
    return rows


def expand_kp_index_to_hourly(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        start = _parse_noaa_time(item["time_tag"])
        kp_value = float(item["kp_index"])
        for offset in range(3):
            rows.append({"ts": start + timedelta(hours=offset), "kp_index": kp_value})
    return rows


def build_space_weather_feature_rows(
    *,
    ts: datetime,
    solar_wind_speed: float,
    imf_bz: float,
    xray_flux: float,
    kp_index: float,
    observed_ts: datetime,
    available_ts: datetime,
    source: str = "noaa_swpc_recent",
    quality_flag: str = "provisional",
) -> list[dict[str, Any]]:
    metric_pairs = [
        ("solar_wind_speed", solar_wind_speed),
        ("imf_bz", imf_bz),
        ("xray_flux", xray_flux),
        ("kp_index", kp_index),
    ]
    return [
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
            "observed_ts": observed_ts,
            "available_ts": available_ts,
            "quality_flag": quality_flag,
        }
        for metric_name, metric_value in metric_pairs
    ]


class SpaceWeatherClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch_json(self, endpoint_key: str) -> Any:
        url = NOAA_SPACE_WEATHER_ENDPOINTS[endpoint_key]
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_plasma(self) -> list[dict[str, Any]]:
        return parse_noaa_table_feed(self.fetch_json("plasma"))

    def fetch_magnetometer(self) -> list[dict[str, Any]]:
        return parse_noaa_table_feed(self.fetch_json("mag"))

    def fetch_xray_flux(self) -> list[dict[str, Any]]:
        return parse_xray_flux_feed(self.fetch_json("xray"))

    def fetch_hourly_kp(self) -> list[dict[str, Any]]:
        return expand_kp_index_to_hourly(self.fetch_json("kp"))
