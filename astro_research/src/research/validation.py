from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.io import read_optional_table


def validate_research_layer(*, root: str | Path, paths: dict[str, str], output_path: str | Path) -> tuple[Path, list[str]]:
    root_path = Path(root)
    warnings: list[str] = []
    checks = []
    for name, relative in paths.items():
        if name == "research_run_manifest":
            manifest_warnings, status = _validate_run_manifest_path(_resolve(root_path, relative))
            warnings.extend(manifest_warnings)
            checks.append((name, 1 if status != "missing_or_empty" else 0, status))
            continue
        frame = read_optional_table(_resolve(root_path, relative))
        if frame.empty:
            warnings.append(f"{name}: missing_or_empty")
            checks.append((name, 0, "missing_or_empty"))
            continue
        duplicate_count = _duplicate_count(name, frame)
        status = "ok" if duplicate_count == 0 else f"duplicates={duplicate_count}"
        if duplicate_count:
            warnings.append(f"{name}: {status}")
        semantic_warnings = _semantic_warnings(name, frame)
        warnings.extend(semantic_warnings)
        if semantic_warnings and status == "ok":
            status = f"warnings={len(semantic_warnings)}"
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
        "data_source_registry": ["ts", "source", "series_id", "asset"],
        "market_asset_coverage": ["ts", "asset", "source"],
        "macro_series_coverage": ["ts", "asset", "source"],
        "macro_daily_observations": ["ts", "series_id", "source"],
        "financial_stress_daily": ["ts", "stress_universe"],
        "research_events": ["event_ts", "event_id"],
        "research_hypotheses": ["ts", "hypothesis_id", "config_hash"],
        "event_study_results_v2": ["run_id", "hypothesis_id", "event_family", "asset", "window_name", "baseline_method", "metric"],
        "event_traceability": ["hypothesis_id", "event_family", "source_table"],
    }.get(name, [])
    if not keys or any(key not in frame.columns for key in keys):
        return 0
    return int(frame.duplicated(keys).sum())


def _semantic_warnings(name: str, frame: pd.DataFrame) -> list[str]:
    warnings = _timing_warnings(name, frame)
    if name == "data_source_registry":
        return warnings + _source_registry_warnings(frame)
    if name == "macro_daily_observations":
        return warnings + _macro_observation_warnings(frame)
    if name in {"market_asset_coverage", "macro_series_coverage"}:
        return warnings + _coverage_warnings(name, frame)
    if name == "event_traceability":
        return warnings + _event_traceability_warnings(frame)
    if name == "event_study_results_v2":
        return warnings + _event_result_warnings(frame)
    return warnings


def _timing_warnings(name: str, frame: pd.DataFrame) -> list[str]:
    timing_sensitive = {
        "market_daily_features",
        "macro_daily_observations",
        "financial_stress_daily",
    }
    if name not in timing_sensitive or frame.empty:
        return []
    warnings = []
    if "available_ts" not in frame.columns:
        warnings.append(f"{name}: available_ts missing; use for historical association only, not point-in-time backtest")
    if "observed_ts" not in frame.columns and name != "market_daily_features":
        warnings.append(f"{name}: observed_ts missing; ts is treated as observation date")
    return warnings


def _source_registry_warnings(frame: pd.DataFrame) -> list[str]:
    warnings = []
    required = {"metadata", "source", "redistribution_allowed", "publication_grade"}
    if "metadata" not in frame.columns:
        return ["data_source_registry: missing metadata column"]
    local = frame[
        (frame.get("source", pd.Series(dtype=str)).astype(str) == "local_csv")
        & (frame.get("source_url", pd.Series(dtype=str)).fillna("").astype(str).str.startswith("local:"))
    ].copy()
    if local.empty:
        return warnings
    metadata = local["metadata"].fillna("").astype(str)
    if metadata.str.len().eq(0).any():
        warnings.append("data_source_registry: local_csv rows missing metadata")
    for token in sorted(required - {"metadata", "source"}):
        if not metadata.str.contains(f"{token}=", regex=False).all():
            warnings.append(f"data_source_registry: local_csv metadata missing `{token}` flag")
    if local["metadata"].fillna("").astype(str).str.contains("is_proxy=True", regex=False).any():
        proxy = local[local["metadata"].fillna("").astype(str).str.contains("is_proxy=True", regex=False)]
        if not proxy["metadata"].fillna("").astype(str).str.contains("not_equivalent_to=", regex=False).all():
            warnings.append("data_source_registry: proxy rows missing not_equivalent_to metadata")
    return warnings


def _macro_observation_warnings(frame: pd.DataFrame) -> list[str]:
    warnings = []
    if "transformed_frequency" not in frame.columns:
        warnings.append("macro_daily_observations: missing transformed_frequency")
    if {"original_frequency", "transformed_frequency", "fill_method"}.issubset(frame.columns):
        transformed = frame[
            frame["original_frequency"].fillna("").astype(str)
            != frame["transformed_frequency"].fillna("").astype(str)
        ]
        if not transformed.empty and transformed["fill_method"].fillna("").astype(str).isin({"", "none"}).any():
            warnings.append("macro_daily_observations: transformed frequency rows require explicit fill_method")
    return warnings


def _coverage_warnings(name: str, frame: pd.DataFrame) -> list[str]:
    warnings = []
    required = {
        "calendar_expected_count",
        "calendar_missing_count",
        "frequency_adjusted_expected_count",
        "frequency_adjusted_missing_count",
        "frequency_adjusted_missing_pct",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        warnings.append(f"{name}: missing coverage audit columns: {','.join(missing)}")
    return warnings


def _event_traceability_warnings(frame: pd.DataFrame) -> list[str]:
    warnings = []
    required = {
        "hypothesis_id",
        "event_family",
        "source_table",
        "eligible_event_count",
        "source_event_id_examples",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        return [f"event_traceability: missing columns: {','.join(missing)}"]
    aspect_hypotheses = {"H003_mars_saturn_hard_aspects", "H004_macro_core_aspect_cluster"}
    present = aspect_hypotheses.intersection(set(frame["hypothesis_id"].astype(str)))
    for hypothesis_id in sorted(present):
        rows = frame[
            (frame["hypothesis_id"].astype(str) == hypothesis_id)
            & (frame["source_table"].astype(str) == "astro_aspect_events")
        ]
        count = int(pd.to_numeric(rows["eligible_event_count"], errors="coerce").fillna(0).sum())
        examples = ",".join(rows["source_event_id_examples"].fillna("").astype(str).tolist())
        if count <= 0:
            warnings.append(f"event_traceability: {hypothesis_id} missing astro_aspect_events eligible events")
        if not examples:
            warnings.append(f"event_traceability: {hypothesis_id} missing source_event_id examples")
    return warnings


def _event_result_warnings(frame: pd.DataFrame) -> list[str]:
    warnings = []
    if "hypothesis_id" not in frame.columns:
        return ["event_study_results_v2: missing hypothesis_id"]
    if frame["hypothesis_id"].fillna("").astype(str).eq("").any():
        warnings.append("event_study_results_v2: blank hypothesis_id")
    if "source_note" in frame.columns:
        source_note = frame["source_note"].fillna("").astype(str)
        if source_note.str.contains("trading signal", case=False, regex=False).any():
            warnings.append("event_study_results_v2: forbidden trading-signal language in source_note")
    return warnings


def _validate_run_manifest_path(path: Path) -> tuple[list[str], str]:
    if not str(path) or not path.exists() or path.is_dir():
        return [f"research_run_manifest: missing_or_empty"], "missing_or_empty"
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"research_run_manifest: invalid json: {exc}"], "warnings=1"
    warnings = _run_manifest_warnings(payload)
    return warnings, "ok" if not warnings else f"warnings={len(warnings)}"


def _run_manifest_warnings(payload: dict) -> list[str]:
    warnings = []
    if payload.get("manifest_version") != "research_run_manifest_v1":
        warnings.append("research_run_manifest: unexpected manifest_version")
    if not str(payload.get("run_id", "")):
        warnings.append("research_run_manifest: missing run_id")
    config = payload.get("config", {}) if isinstance(payload.get("config", {}), dict) else {}
    if len(str(config.get("sha256", ""))) != 64:
        warnings.append("research_run_manifest: missing config sha256")
    git = payload.get("git", {}) if isinstance(payload.get("git", {}), dict) else {}
    if not str(git.get("commit", "")):
        warnings.append("research_run_manifest: missing git commit")
    inputs = payload.get("inputs", []) if isinstance(payload.get("inputs", []), list) else []
    for name in ("research_events", "market_daily_features", "research_hypotheses"):
        rows = [item for item in inputs if isinstance(item, dict) and item.get("name") == name]
        if not rows:
            warnings.append(f"research_run_manifest: missing input fingerprint {name}")
        elif len(str(rows[0].get("schema_sha256", ""))) != 64:
            warnings.append(f"research_run_manifest: missing schema fingerprint for {name}")
    outputs = payload.get("outputs", []) if isinstance(payload.get("outputs", []), list) else []
    artifacts = {str(item.get("artifact", "")) for item in outputs if isinstance(item, dict)}
    for artifact in ("results.parquet", "event_traceability.csv", "warnings.json", "config_snapshot.yaml"):
        if artifact not in artifacts:
            warnings.append(f"research_run_manifest: missing output artifact {artifact}")
    if payload.get("association_only") is not True:
        warnings.append("research_run_manifest: association_only must be true for exploratory research outputs")
    return warnings


def _resolve(root: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
