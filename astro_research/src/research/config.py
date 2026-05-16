from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astro_daily.config import _parse_simple_yaml


@dataclass(frozen=True)
class EventStudyConfig:
    run_id: str
    data_version: str
    calc_version: str
    random_seed: int
    bootstrap_samples: int
    placebo_samples: int
    market_features_path: str
    astro_event_windows_path: str
    astro_daily_features_path: str
    aspect_chunks_dir: str
    event_groups: dict[str, dict[str, Any]]
    windows: tuple[str, ...]
    baseline_types: tuple[str, ...]
    exclude_event_windows: bool


def load_event_study_config(path: str | Path) -> EventStudyConfig:
    raw = _parse_simple_yaml(Path(path).read_text())
    run = raw.get("run", {})
    inputs = raw.get("inputs", {})
    baseline = raw.get("baseline", {})
    return EventStudyConfig(
        run_id=str(run.get("run_id", "event_study_v1")),
        data_version=str(run.get("data_version", "market_daily_v1")),
        calc_version=str(run.get("calc_version", "event_study_v1")),
        random_seed=int(run.get("random_seed", 42)),
        bootstrap_samples=int(run.get("bootstrap_samples", 1000)),
        placebo_samples=int(run.get("placebo_samples", 1000)),
        market_features_path=str(inputs.get("market_features_path", "")),
        astro_event_windows_path=str(inputs.get("astro_event_windows_path", "")),
        astro_daily_features_path=str(inputs.get("astro_daily_features_path", "")),
        aspect_chunks_dir=str(inputs.get("aspect_chunks_dir", "")),
        event_groups=raw.get("event_groups", {}),
        windows=tuple(str(value) for value in raw.get("windows", ("-7,7",))),
        baseline_types=tuple(str(value) for value in baseline.get("types", ("all_non_event",))),
        exclude_event_windows=bool(baseline.get("exclude_event_windows", True)),
    )
