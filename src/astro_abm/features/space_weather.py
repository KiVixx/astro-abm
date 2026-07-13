from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

NOAA_SPACE_WEATHER_ENDPOINTS = {
    "plasma": "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json",
    "mag": "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json",
    "xray": "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json",
    "kp": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
}


def _parse_noaa_time(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    if "T" in value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
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


def parse_rtsw_wind_feed(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        time_tag = item.get("time_tag")
        if not isinstance(time_tag, str):
            continue
        speed = _try_float(item.get("proton_speed"))
        if speed is None:
            continue
        rows.append(
            {
                "time_tag": _parse_noaa_time(time_tag),
                "speed": speed,
                "source": item.get("source"),
                "overall_quality": item.get("overall_quality"),
            }
        )
    return rows


def parse_rtsw_mag_feed(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        time_tag = item.get("time_tag")
        if not isinstance(time_tag, str):
            continue
        bz_gsm = _try_float(item.get("bz_gsm"))
        if bz_gsm is None:
            continue
        rows.append(
            {
                "time_tag": _parse_noaa_time(time_tag),
                "bz_gsm": bz_gsm,
                "source": item.get("source"),
                "overall_quality": item.get("overall_quality"),
            }
        )
    return rows


def parse_plasma_feed(payload: Any) -> list[dict[str, Any]]:
    if _looks_like_table_feed(payload):
        return parse_noaa_table_feed(payload)
    if isinstance(payload, list):
        return parse_rtsw_wind_feed([item for item in payload if isinstance(item, dict)])
    return []


def parse_magnetometer_feed(payload: Any) -> list[dict[str, Any]]:
    if _looks_like_table_feed(payload):
        return parse_noaa_table_feed(payload)
    if isinstance(payload, list):
        return parse_rtsw_mag_feed([item for item in payload if isinstance(item, dict)])
    return []


def parse_xray_flux_feed(payload: list[dict[str, Any]], energy_channel: str = "0.1-0.8nm") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        if item.get("energy") != energy_channel:
            continue
        flux = _try_float(item.get("flux"))
        if flux is None:
            continue
        rows.append(
            {
                "time_tag": _parse_noaa_time(item["time_tag"]),
                "energy": item["energy"],
                "flux": flux,
            }
        )
    return rows


def expand_kp_index_to_hourly(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        start = _parse_noaa_time(item["time_tag"])
        kp_value = _try_float(item.get("kp_index", item.get("Kp")))
        if kp_value is None:
            continue
        for offset in range(3):
            rows.append({"ts": start + timedelta(hours=offset), "kp_index": kp_value})
    return rows


def _try_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_like_table_feed(payload: Any) -> bool:
    return (
        isinstance(payload, list)
        and bool(payload)
        and isinstance(payload[0], list)
    )


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
    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        timeout_seconds: float = 30,
        max_attempts: int = 3,
        retry_sleep_seconds: float = 1.0,
    ):
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.retry_sleep_seconds = max(0.0, retry_sleep_seconds)

    def fetch_json(self, endpoint_key: str) -> Any:
        url = NOAA_SPACE_WEATHER_ENDPOINTS[endpoint_key]
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                return _load_noaa_json(response.text)
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.retry_sleep_seconds * attempt)
        assert last_error is not None
        raise last_error

    def fetch_plasma(self) -> list[dict[str, Any]]:
        return parse_plasma_feed(self.fetch_json("plasma"))

    def fetch_magnetometer(self) -> list[dict[str, Any]]:
        return parse_magnetometer_feed(self.fetch_json("mag"))

    def fetch_xray_flux(self) -> list[dict[str, Any]]:
        return parse_xray_flux_feed(self.fetch_json("xray"))

    def fetch_hourly_kp(self) -> list[dict[str, Any]]:
        return expand_kp_index_to_hourly(self.fetch_json("kp"))


def _load_noaa_json(text: str) -> Any:
    decoder = json.JSONDecoder()
    value, end = decoder.raw_decode(text.lstrip())
    trailing = text.lstrip()[end:].strip()
    if trailing:
        # NOAA live endpoints occasionally append a second payload or diagnostic
        # text. Keep the first complete JSON document instead of dropping the hour.
        return value
    return value
