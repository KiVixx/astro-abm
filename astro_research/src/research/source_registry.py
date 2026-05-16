from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from astro_daily.config import _parse_simple_yaml


@dataclass(frozen=True)
class SourceRegistry:
    data_version: str
    rows: pd.DataFrame
    warnings: tuple[str, ...]


def build_source_registry(config_path: str | Path, *, created_at: datetime | None = None, root: str | Path | None = None) -> SourceRegistry:
    config_path = Path(config_path)
    root_path = Path(root or config_path.parents[2])
    raw = _parse_simple_yaml(config_path.read_text())
    data_version = str(raw.get("dataset", {}).get("data_version", "research_sources_v1"))
    created_at = created_at or datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for source, values in raw.get("sources", {}).items():
        series_ids = _split_csv(values.get("canonical_for", ""))
        if not series_ids:
            series_ids = [source]
        for series_id in series_ids:
            rows.append(
                {
                    "ts": created_at,
                    "source": source,
                    "provider": str(values.get("provider", "")),
                    "series_id": series_id,
                    "asset": _asset_from_series(series_id),
                    "frequency": str(values.get("frequency", "")),
                    "coverage_start_ts": pd.NaT,
                    "coverage_end_ts": pd.NaT,
                    "is_canonical": bool(values.get("is_canonical", False)),
                    "requires_api_key": bool(values.get("requires_api_key", False)),
                    "license_note": str(values.get("license_note", "")),
                    "source_url": str(values.get("source_url", "")),
                    "metadata": "",
                    "data_version": data_version,
                    "created_at": created_at,
                }
            )
    rows.extend(_local_csv_rows(root_path=root_path, created_at=created_at, data_version=data_version, warnings=warnings))
    if not rows:
        warnings.append("No sources configured.")
    return SourceRegistry(data_version=data_version, rows=pd.DataFrame(rows), warnings=tuple(warnings))


def write_source_registry_report(registry: SourceRegistry, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Data Source Registry",
        "",
        f"data_version: `{registry.data_version}`",
        "",
        "| source | provider | series_id | canonical | requires_api_key | metadata |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in registry.rows.itertuples(index=False):
        metadata = getattr(row, "metadata", "")
        lines.append(f"| {row.source} | {row.provider} | {row.series_id} | {row.is_canonical} | {row.requires_api_key} | {metadata} |")
    if registry.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in registry.warnings)
    output.write_text("\n".join(lines) + "\n")
    return output


def _split_csv(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _asset_from_series(series_id: str) -> str:
    mapping = {
        "CBBTCUSD": "BTC",
        "CBETHUSD": "ETH",
        "SP500": "SPX",
        "NASDAQ100": "NDX",
        "DGS10": "US10Y",
        "DGS2": "US2Y",
        "BAMLH0A0HYM2": "HY_OAS",
    }
    return mapping.get(series_id, series_id)


def _local_csv_rows(*, root_path: Path, created_at: datetime, data_version: str, warnings: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config_name, section_name in (("market_assets_real.yaml", "assets"), ("macro_series.yaml", "series")):
        path = root_path / "astro_research" / "configs" / config_name
        if not path.exists():
            continue
        raw = _parse_simple_yaml(path.read_text())
        for name, values in raw.get(section_name, {}).items():
            local_path = values.get("path") if values.get("source") == "local_csv" else values.get("fallback_path")
            if not local_path:
                continue
            license_note = str(values.get("license_note", raw.get("sources", {}).get("local_csv", {}).get("license_note", "")))
            if not license_note:
                warnings.append(f"{name}: local_csv license_note missing")
            target = Path(str(local_path))
            if not target.is_absolute():
                target = root_path / target
            status = "available" if target.exists() else "unavailable_local_file"
            if status != "available":
                warnings.append(f"{name}: unavailable_local_file: {local_path}")
            rows.append(
                {
                    "ts": created_at,
                    "source": "local_csv",
                    "provider": "LocalCSVProvider",
                    "series_id": str(values.get("symbol", name)),
                    "asset": name,
                    "frequency": str(values.get("frequency", values.get("original_frequency", "daily"))),
                    "coverage_start_ts": pd.NaT,
                    "coverage_end_ts": pd.NaT,
                    "is_canonical": bool(values.get("source") == "local_csv" or values.get("fallback_source") == "local_csv"),
                    "requires_api_key": False,
                    "license_note": license_note or "missing_license_note",
                    "source_url": str(target if status == "available" else f"unavailable_local_file:{local_path}"),
                    "metadata": _local_metadata(name=name, values=values),
                    "data_version": data_version,
                    "created_at": created_at,
                }
            )
    return rows


def _local_metadata(*, name: str, values: dict[str, Any]) -> str:
    source_note = str(values.get("license_note", "")).lower()
    metadata: dict[str, Any] = {
        "local_research_only": True,
        "redistribution_allowed": False,
        "publication_grade": False,
        "licensing_review_required": True,
    }
    if name in {"SPX", "DXY"} or "yahoo" in source_note:
        metadata.update(
            {
                "provider_family": "Yahoo",
                "local_research_only": True,
                "redistribution_allowed": False,
                "publication_grade": False,
                "licensing_review_required": True,
            }
        )
    if name == "Gold" or "lbma" in source_note or "ice" in source_note:
        metadata.update(
            {
                "provider_family": "LBMA_ICE",
                "redistribution_allowed": False,
                "publication_grade": False,
                "licensing_review_required": True,
            }
        )
    if name == "BAMLH0A0HYM2":
        metadata.update(
            {
                "proxy_type": "BAA_MINUS_AAA",
                "not_equivalent_to": "ICE_BofA_HY_OAS",
                "original_frequency": str(values.get("original_frequency", "monthly")),
                "fill_method": "business_daily_forward_fill",
            }
        )
    return ";".join(f"{key}={value}" for key, value in sorted(metadata.items()))
