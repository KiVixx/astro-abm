from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

from .aspect_profiles import pair_slug
from .aspects import aspect_event_rows, aspect_event_windows, scan_aspect_events_for_pair
from .calendar import parse_date, utc_midnight
from .config import load_astro_daily_config
from .swiss_ephemeris_backend import SwissEphemerisBackend

ASPECT_EVENT_COLUMNS = [
    "exact_ts",
    "dataset_id",
    "event_id",
    "body_a",
    "body_b",
    "aspect_name",
    "aspect_deg",
    "exact_delta_deg",
    "relative_speed_deg_day",
    "applying_before",
    "calc_version",
    "source_note",
]

EVENT_WINDOW_COLUMNS = [
    "ts",
    "dataset_id",
    "event_id",
    "event_type",
    "body",
    "body_a",
    "body_b",
    "aspect_name",
    "phase_name",
    "exact_ts",
    "exact_date_ts",
    "rel_day",
    "window_name",
    "window_days",
    "weight",
    "calc_version",
]


@dataclass(frozen=True)
class AspectBuildTask:
    year: int
    pair: tuple[str, str]
    start: date
    end: date


def years_for_range(start: date, end: date) -> tuple[int, ...]:
    return tuple(range(start.year, end.year + 1))


def aspect_tasks(*, pairs: Iterable[tuple[str, str]], start: date, end: date) -> tuple[AspectBuildTask, ...]:
    tasks = []
    for year in years_for_range(start, end):
        year_start = max(start, date(year, 1, 1))
        year_end = min(end, date(year, 12, 31))
        for pair in pairs:
            tasks.append(AspectBuildTask(year=year, pair=pair, start=year_start, end=year_end))
    return tuple(tasks)


def build_aspect_chunks(
    *,
    config_path: str | Path,
    output_dir: str | Path,
    tasks: Iterable[AspectBuildTask],
    skip_existing: bool = False,
    resume: bool = False,
    workers: int = 1,
    write_parquet: bool = True,
) -> list[dict]:
    output = Path(output_dir)
    task_list = tuple(tasks)
    checkpoint = _load_checkpoint(output) if resume else {}
    pending = [
        task
        for task in task_list
        if not (skip_existing and aspect_chunk_complete(output, task))
        and not (resume and _task_key(task) in checkpoint and aspect_chunk_complete(output, task))
    ]
    if workers <= 1:
        results = [_build_one_task(str(config_path), str(output), task, write_parquet) for task in pending]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_build_one_task, str(config_path), str(output), task, write_parquet) for task in pending]
            for future in as_completed(futures):
                results.append(future.result())
    if resume:
        checkpoint.update({_task_key(task): True for task in pending})
        _save_checkpoint(output, checkpoint)
    skipped = [{"year": task.year, "pair": pair_slug(task.pair), "status": "skipped"} for task in task_list if task not in pending]
    return skipped + sorted(results, key=lambda row: (row["year"], row["pair"]))


def aspect_chunk_complete(output_dir: str | Path, task: AspectBuildTask) -> bool:
    chunk = aspect_chunk_dir(output_dir, task)
    return (chunk / "astro_aspect_events.csv").exists() and (chunk / "astro_event_windows.csv").exists()


def aspect_chunk_dir(output_dir: str | Path, task: AspectBuildTask) -> Path:
    return Path(output_dir) / "aspects" / f"year={task.year}" / f"body_pair={pair_slug(task.pair)}"


def validate_aspect_chunks(
    *,
    output_dir: str | Path,
    tasks: Iterable[AspectBuildTask],
    expected_min_ts: datetime,
    expected_max_ts: datetime,
) -> tuple[str, ...]:
    warnings = []
    seen_events = set()
    seen_windows = set()
    for task in tasks:
        chunk = aspect_chunk_dir(output_dir, task)
        events_path = chunk / "astro_aspect_events.csv"
        windows_path = chunk / "astro_event_windows.csv"
        if not events_path.exists() or not windows_path.exists():
            warnings.append(f"missing aspect chunk: year={task.year} pair={pair_slug(task.pair)}")
            continue
        events = _read_csv(events_path)
        windows = _read_csv(windows_path)
        if not events.empty:
            duplicate_events = events[events.duplicated(["dataset_id", "event_id"])]
            if len(duplicate_events):
                warnings.append(f"duplicate event_id in chunk {task.year}/{pair_slug(task.pair)}: {len(duplicate_events)}")
            for event_id in events["event_id"].astype(str):
                if event_id in seen_events:
                    warnings.append(f"duplicate event_id across chunks: {event_id}")
                seen_events.add(event_id)
            exact_ts = pd.to_datetime(events["exact_ts"], utc=True)
            if (exact_ts < expected_min_ts).any() or (exact_ts > expected_max_ts).any():
                warnings.append(f"exact aspect range violation: year={task.year} pair={pair_slug(task.pair)}")
        if not windows.empty:
            duplicate_windows = windows[windows.duplicated(["ts", "dataset_id", "event_id"])]
            if len(duplicate_windows):
                warnings.append(f"duplicate event windows in chunk {task.year}/{pair_slug(task.pair)}: {len(duplicate_windows)}")
            for key in windows[["ts", "dataset_id", "event_id"]].astype(str).itertuples(index=False, name=None):
                if key in seen_windows:
                    warnings.append(f"duplicate event window across chunks: {key}")
                seen_windows.add(key)
    return tuple(warnings)


def _build_one_task(config_path: str, output_dir: str, task: AspectBuildTask, write_parquet: bool) -> dict:
    started = time.perf_counter()
    config = load_astro_daily_config(config_path)
    backend = SwissEphemerisBackend()
    start_ts = utc_midnight(task.start)
    end_ts = utc_midnight(task.end) + timedelta(days=1)
    events = scan_aspect_events_for_pair(
        backend=backend,
        body_a=task.pair[0],
        body_b=task.pair[1],
        major_aspects=config.major_aspects,
        start_ts=start_ts,
        end_ts=end_ts,
        step_hours=12,
        tolerance_seconds=120,
    )
    rows = aspect_event_rows(events, dataset_id=config.dataset.dataset_id, calc_version=config.dataset.calc_version)
    windows = aspect_event_windows(
        events,
        dataset_id=config.dataset.dataset_id,
        calc_version=config.dataset.calc_version,
        window_days_values=tuple(config.clusters.aspect_cluster_windows_days),
    )
    chunk = aspect_chunk_dir(output_dir, task)
    chunk.mkdir(parents=True, exist_ok=True)
    event_frame = pd.DataFrame(rows, columns=ASPECT_EVENT_COLUMNS)
    window_frame = pd.DataFrame(windows, columns=EVENT_WINDOW_COLUMNS)
    event_frame.to_csv(chunk / "astro_aspect_events.csv", index=False)
    window_frame.to_csv(chunk / "astro_event_windows.csv", index=False)
    if write_parquet:
        event_frame.to_parquet(chunk / "astro_aspect_events.parquet", index=False)
        window_frame.to_parquet(chunk / "astro_event_windows.parquet", index=False)
    return {
        "year": task.year,
        "pair": pair_slug(task.pair),
        "events": len(rows),
        "windows": len(windows),
        "seconds": round(time.perf_counter() - started, 4),
        "status": "built",
    }


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _task_key(task: AspectBuildTask) -> str:
    return f"{task.year}:{pair_slug(task.pair)}"


def _load_checkpoint(output_dir: Path) -> dict:
    path = output_dir / "_checkpoints" / "aspect_build.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_checkpoint(output_dir: Path, checkpoint: dict) -> None:
    path = output_dir / "_checkpoints" / "aspect_build.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True))
