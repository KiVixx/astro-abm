from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import requests


NOAA_GOES_XRS_BASE_URL = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes"
GOES_XRS_EPOCH = datetime(2000, 1, 1, 12, tzinfo=UTC)


class GoesXrayClient:
    def __init__(
        self,
        base_url: str = NOAA_GOES_XRS_BASE_URL,
        session: requests.Session | None = None,
        request_timeout: float | tuple[float, float] = (15, 120),
        healthcheck_timeout: float = 8,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.request_timeout = request_timeout
        self.healthcheck_timeout = healthcheck_timeout

    def year_path(self, *, year: int, satellite: str, cache_dir: Path) -> Path:
        filename = f"sci_xrsf-l2-avg1m_{satellite}_y{year}_v2-2-1.nc"
        return cache_dir / filename

    def is_year_cached(self, *, year: int, satellite: str, cache_dir: Path) -> bool:
        path = self.year_path(year=year, satellite=satellite, cache_dir=cache_dir)
        return path.exists() and path.stat().st_size > 0

    def archive_healthcheck(self) -> tuple[bool, str]:
        try:
            with self.session.get(f"{self.base_url}/", stream=True, timeout=self.healthcheck_timeout) as response:
                response.close()
                if response.status_code >= 500:
                    return False, f"http_{response.status_code}"
                return True, f"http_{response.status_code}"
        except requests.RequestException as exc:
            return False, f"{type(exc).__name__}:{exc}"

    def download_year(self, *, year: int, satellite: str, cache_dir: Path) -> Path:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.year_path(year=year, satellite=satellite, cache_dir=cache_dir)
        if path.exists() and path.stat().st_size > 0:
            return path

        filename = path.name
        goes_dir = satellite.replace("g", "goes")
        url = f"{self.base_url}/{goes_dir}/l2/data/xrsf-l2-avg1m_science/{filename}"
        with self.session.get(url, stream=True, timeout=self.request_timeout) as response:
            response.raise_for_status()
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
            tmp_path.replace(path)
        return path


def select_goes_xray_satellite(year: int) -> str:
    return "g16" if year <= 2024 else "g18"


def read_goes_xray_hourly_records(
    path: Path,
    *,
    start_utc: datetime,
    end_utc: datetime,
    satellite: str,
) -> list[dict[str, Any]]:
    buckets: dict[datetime, list[float]] = defaultdict(list)
    with h5py.File(path, "r") as handle:
        times = handle["time"][:]
        fluxes = handle["xrsb_flux"][:]

    finite_mask = np.isfinite(times) & np.isfinite(fluxes) & (fluxes > 0) & (fluxes != -9999.0)
    for seconds, flux in zip(times[finite_mask], fluxes[finite_mask], strict=False):
        ts = GOES_XRS_EPOCH + timedelta(seconds=float(seconds))
        if ts < start_utc or ts >= end_utc:
            continue
        bucket = ts.replace(minute=0, second=0, microsecond=0)
        buckets[bucket].append(float(flux))

    return [
        {
            "ts": ts,
            "xray_flux": float(np.mean(values)),
            "sample_count": len(values),
            "satellite": satellite,
        }
        for ts, values in sorted(buckets.items())
        if values
    ]


def build_goes_xray_feature_rows(records: Iterable[dict[str, Any]], *, source: str = "noaa_goes_xrs") -> list[dict[str, Any]]:
    rows = []
    for record in records:
        ts = record["ts"]
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
                "metric_name": "xray_flux",
                "metric_value": record["xray_flux"],
                "metric_value_2": float(record["sample_count"]),
                "observed_ts": ts,
                "available_ts": ts,
                "quality_flag": "authoritative",
                "notes": f"satellite={record['satellite']}; aggregation=hourly_mean_1m_xrsb_flux",
            }
        )
    return rows
