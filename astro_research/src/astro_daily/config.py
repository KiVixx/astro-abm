from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .calendar import parse_date


@dataclass(frozen=True)
class DatasetConfig:
    dataset_id: str
    calc_version: str
    timezone: str
    daily_sample_time_utc: str
    target_start: date
    target_end: date
    buffer_days: int

    @property
    def calculation_start(self) -> date:
        return self.target_start - timedelta(days=self.buffer_days)

    @property
    def calculation_end(self) -> date:
        return self.target_end + timedelta(days=self.buffer_days)


@dataclass(frozen=True)
class RetrogradeConfig:
    station_scan_step_hours: int
    station_refine_tolerance_seconds: int
    station_phase_days: int
    pre_post_window_days: int
    event_study_window_days: int


@dataclass(frozen=True)
class ClusterConfig:
    station_cluster_windows_days: tuple[int, ...]
    aspect_cluster_windows_days: tuple[int, ...]
    weighted_pressure_half_life_days: int


@dataclass(frozen=True)
class AstroDailyConfig:
    dataset: DatasetConfig
    position_bodies: tuple[str, ...]
    retrograde_bodies: tuple[str, ...]
    aspect_bodies: tuple[str, ...]
    major_aspects: dict[str, int]
    aspect_orbs_deg: dict[str, float]
    retrograde: RetrogradeConfig
    clusters: ClusterConfig
    oob_threshold_deg: float
    ephemeris_backend: str = "swiss_ephemeris"


def load_astro_daily_config(path: str | Path) -> AstroDailyConfig:
    raw = _parse_simple_yaml(Path(path).read_text())
    dataset = raw["dataset"]
    retrograde = raw["retrograde"]
    clusters = raw["clusters"]
    weighted_pressure = clusters.get("weighted_pressure", {})
    return AstroDailyConfig(
        dataset=DatasetConfig(
            dataset_id=str(dataset["dataset_id"]),
            calc_version=str(dataset["calc_version"]),
            timezone=str(dataset.get("timezone", "UTC")),
            daily_sample_time_utc=str(dataset.get("daily_sample_time_utc", "00:00:00")),
            target_start=parse_date(str(dataset["target_start"])),
            target_end=parse_date(str(dataset["target_end"])),
            buffer_days=int(dataset.get("buffer_days", 400)),
        ),
        position_bodies=tuple(_title_case_items(raw["bodies"]["position_bodies"])),
        retrograde_bodies=tuple(_title_case_items(raw["bodies"]["retrograde_bodies"])),
        aspect_bodies=tuple(_title_case_items(raw.get("aspects", {}).get("aspect_bodies", ()))),
        major_aspects={str(key): int(value) for key, value in raw.get("aspects", {}).get("major_aspects", {}).items()},
        aspect_orbs_deg={str(key): float(value) for key, value in raw.get("aspects", {}).get("default_orbs_deg", {}).items()},
        retrograde=RetrogradeConfig(
            station_scan_step_hours=int(retrograde.get("station_scan_step_hours", 6)),
            station_refine_tolerance_seconds=int(retrograde.get("station_refine_tolerance_seconds", 60)),
            station_phase_days=int(retrograde.get("station_phase_days", 7)),
            pre_post_window_days=int(retrograde.get("pre_post_window_days", 14)),
            event_study_window_days=int(retrograde.get("event_study_window_days", 30)),
        ),
        clusters=ClusterConfig(
            station_cluster_windows_days=tuple(int(value) for value in clusters.get("station_cluster_windows_days", (3, 7, 14))),
            aspect_cluster_windows_days=tuple(int(value) for value in clusters.get("aspect_cluster_windows_days", (3, 7, 14))),
            weighted_pressure_half_life_days=int(weighted_pressure.get("half_life_days", 3)),
        ),
        oob_threshold_deg=float(raw.get("declination", {}).get("fallback_oob_threshold_deg", 23.4367)),
        ephemeris_backend=str(raw.get("ephemeris", {}).get("backend", "swiss_ephemeris")),
    )


def _title_case_items(values: Any) -> list[str]:
    return [str(value).strip().title() for value in values]


def _parse_simple_yaml(text: str) -> dict:
    lines = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line.strip()))
    value, index = _parse_block(lines, 0, 0)
    if index != len(lines) or not isinstance(value, dict):
        raise ValueError("Invalid astro daily config.")
    return value


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith("- "):
        values = []
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent != indent or not content.startswith("- "):
                break
            item = content[2:].strip()
            values.append(_parse_scalar(item))
            index += 1
        return values, index

    result = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent != indent or content.startswith("- "):
            break
        if ":" not in content:
            raise ValueError(f"Invalid config line: {content}")
        key, raw_value = content.split(":", 1)
        raw_value = raw_value.strip()
        index += 1
        if raw_value:
            result[key] = _parse_scalar(raw_value)
        else:
            result[key], index = _parse_block(lines, index, indent + 2)
    return result, index


def _parse_scalar(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
