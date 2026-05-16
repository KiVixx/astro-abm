from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from astro_daily.config import _parse_simple_yaml


HYPOTHESIS_COLUMNS = [
    "ts",
    "hypothesis_id",
    "title",
    "status",
    "event_family",
    "primary_assets",
    "primary_metrics",
    "windows",
    "expected_direction",
    "baseline_methods",
    "multiple_testing_group",
    "min_events",
    "min_observations",
    "config_hash",
    "git_commit",
    "created_at",
    "updated_at",
]


@dataclass(frozen=True)
class HypothesisRegistry:
    rows: pd.DataFrame
    config_hash: str
    git_commit: str


def register_hypotheses(config_path: str | Path, *, git_commit: str = "auto", now: datetime | None = None) -> HypothesisRegistry:
    path = Path(config_path)
    text = path.read_text()
    raw = _parse_simple_yaml(text)
    now = now or datetime.now(UTC)
    config_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    if git_commit == "auto":
        git_commit = _git_commit(path)
    rows = []
    for hypothesis_id, values in raw.get("hypotheses", {}).items():
        rows.append(
            {
                "ts": now,
                "hypothesis_id": hypothesis_id,
                "title": str(values.get("title", "")),
                "status": str(values.get("status", "active")),
                "event_family": str(values.get("event_family", "")),
                "primary_assets": str(values.get("primary_assets", "")),
                "primary_metrics": str(values.get("primary_metrics", "")),
                "windows": str(values.get("windows", "")),
                "expected_direction": str(values.get("expected_direction", "")),
                "baseline_methods": str(values.get("baseline_methods", "")),
                "multiple_testing_group": str(values.get("multiple_testing_group", "")),
                "min_events": int(values.get("min_events", 0)),
                "min_observations": int(values.get("min_observations", 0)),
                "config_hash": config_hash,
                "git_commit": git_commit,
                "created_at": now,
                "updated_at": now,
            }
        )
    return HypothesisRegistry(pd.DataFrame(rows, columns=HYPOTHESIS_COLUMNS), config_hash, git_commit)


def export_hypotheses(registry: HypothesisRegistry, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "research_hypotheses.csv"
    parquet_path = output / "research_hypotheses.parquet"
    registry.rows.to_csv(csv_path, index=False)
    registry.rows.to_parquet(parquet_path, index=False)
    return {"csv": csv_path, "parquet": parquet_path}


def expected_direction_map(value: str) -> dict[str, str]:
    result = {}
    for part in str(value or "").split(","):
        if ":" in part:
            key, direction = part.split(":", 1)
            result[key.strip()] = direction.strip()
    return result


def _git_commit(path: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=path.parents[2], text=True).strip()
    except Exception:
        return "unknown"
