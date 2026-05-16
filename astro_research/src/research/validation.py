from __future__ import annotations

from pathlib import Path

import pandas as pd

from research.io import read_optional_table


def validate_research_layer(*, root: str | Path, paths: dict[str, str], output_path: str | Path) -> tuple[Path, list[str]]:
    root_path = Path(root)
    warnings: list[str] = []
    checks = []
    for name, relative in paths.items():
        frame = read_optional_table(_resolve(root_path, relative))
        if frame.empty:
            warnings.append(f"{name}: missing_or_empty")
            checks.append((name, 0, "missing_or_empty"))
            continue
        duplicate_count = _duplicate_count(name, frame)
        status = "ok" if duplicate_count == 0 else f"duplicates={duplicate_count}"
        if duplicate_count:
            warnings.append(f"{name}: {status}")
        checks.append((name, len(frame), status))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Research Layer Validation", "", "| table | rows | status |", "|---|---:|---|"]
    lines.extend(f"| {name} | {rows} | {status} |" for name, rows, status in checks)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    output.write_text("\n".join(lines) + "\n")
    return output, warnings


def _duplicate_count(name: str, frame: pd.DataFrame) -> int:
    keys = {
        "market_daily_features": ["ts", "asset", "source"],
        "macro_daily_observations": ["ts", "series_id", "source"],
        "financial_stress_daily": ["ts", "stress_universe"],
        "research_events": ["event_ts", "event_id"],
        "research_hypotheses": ["ts", "hypothesis_id", "config_hash"],
        "event_study_results_v2": ["run_id", "hypothesis_id", "event_family", "asset", "window_name", "baseline_method", "metric"],
    }.get(name, [])
    if not keys or any(key not in frame.columns for key in keys):
        return 0
    return int(frame.duplicated(keys).sum())


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
