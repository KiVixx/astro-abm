from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from astro_daily.ingest_questdb import TIMESTAMP_COLUMNS


DUCKDB_OUTPUT = Path("astro_research/output/duckdb/astro_research_full_history.duckdb")

CORE_SNAPSHOT_TABLES = {
    "astro_daily_1926_2025": (
        "astro_daily_positions",
        "astro_daily_facts",
        "astro_retrograde_cycles",
        "astro_aspect_events",
        "astro_moon_phase_events",
        "astro_event_windows",
        "astro_daily_features",
    ),
    "source_registry": ("data_source_registry",),
    "market_daily": ("market_daily_bars", "market_daily_features", "market_asset_coverage"),
    "macro_daily": ("macro_daily_observations", "macro_series_coverage", "fred_diagnostics"),
    "financial_stress": ("financial_stress_daily", "financial_stress_component_coverage"),
    "research_events": ("research_events",),
    "research_hypotheses": ("research_hypotheses",),
}

TIMESTAMP_COLUMN_OVERRIDES = {
    **TIMESTAMP_COLUMNS,
    "macro_series_coverage": "ts",
    "fred_diagnostics": "requested_at",
    "financial_stress_component_coverage": "ts",
    "aspect_chunk_astro_aspect_events": "exact_ts",
    "aspect_chunk_astro_event_windows": "ts",
}


@dataclass(frozen=True)
class SnapshotSource:
    table_name: str
    paths: tuple[Path, ...]
    source_format: str

    @property
    def source_path(self) -> str:
        if len(self.paths) == 1:
            return str(self.paths[0])
        return ";".join(str(path) for path in self.paths)


@dataclass(frozen=True)
class DuckDBBuildResult:
    output_path: Path
    manifest: pd.DataFrame


def discover_snapshot_sources(snapshot_root: str | Path, *, include_aspect_chunks: bool = True) -> list[SnapshotSource]:
    root = Path(snapshot_root)
    sources: list[SnapshotSource] = []
    for directory, tables in CORE_SNAPSHOT_TABLES.items():
        base = root / directory
        for table in tables:
            source = _single_table_source(base, table)
            if source:
                sources.append(source)

    if include_aspect_chunks:
        sources.extend(_aspect_chunk_sources(root))
    return sources


def build_duckdb_store(
    *,
    snapshot_root: str | Path,
    output_path: str | Path,
    include_aspect_chunks: bool = True,
    overwrite: bool = True,
) -> DuckDBBuildResult:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("duckdb is required. Run `uv sync` after updating dependencies.") from exc

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and overwrite:
        output.unlink()

    sources = discover_snapshot_sources(snapshot_root, include_aspect_chunks=include_aspect_chunks)
    manifest_rows: list[dict[str, object]] = []
    with duckdb.connect(str(output)) as connection:
        for source in sources:
            _create_table(connection, source)
            manifest_rows.append(_manifest_row(connection, source))
        manifest = pd.DataFrame(manifest_rows, columns=_manifest_columns())
        connection.register("_research_store_manifest_df", manifest)
        connection.execute('CREATE OR REPLACE TABLE "research_store_manifest" AS SELECT * FROM _research_store_manifest_df')

    return DuckDBBuildResult(output_path=output, manifest=manifest)


def _single_table_source(base: Path, table: str) -> SnapshotSource | None:
    parquet = base / f"{table}.parquet"
    if parquet.exists() and parquet.stat().st_size > 0:
        return SnapshotSource(table_name=table, paths=(parquet,), source_format="parquet")
    csv = base / f"{table}.csv"
    if csv.exists() and csv.stat().st_size > 0:
        return SnapshotSource(table_name=table, paths=(csv,), source_format="csv")
    return None


def _aspect_chunk_sources(root: Path) -> list[SnapshotSource]:
    aspect_roots = sorted(path for path in root.glob("aspect_chunks*/**/aspects") if path.is_dir())
    event_files = _prefer_partition_format(aspect_roots, "astro_aspect_events")
    window_files = _prefer_partition_format(aspect_roots, "astro_event_windows")
    sources = []
    if event_files:
        sources.append(SnapshotSource("aspect_chunk_astro_aspect_events", event_files[1], event_files[0]))
    if window_files:
        sources.append(SnapshotSource("aspect_chunk_astro_event_windows", window_files[1], window_files[0]))
    return sources


def _prefer_partition_format(roots: Iterable[Path], table: str) -> tuple[str, tuple[Path, ...]] | None:
    parquet_files: list[Path] = []
    csv_files: list[Path] = []
    for root in roots:
        parquet_files.extend(root.rglob(f"{table}.parquet"))
        csv_files.extend(root.rglob(f"{table}.csv"))
    if parquet_files:
        return "parquet", tuple(sorted(path for path in parquet_files if path.stat().st_size > 0))
    if csv_files:
        return "csv", tuple(sorted(path for path in csv_files if path.stat().st_size > 0))
    return None


def _create_table(connection, source: SnapshotSource) -> None:
    table = _quote_ident(source.table_name)
    if source.source_format == "parquet":
        reader = f"read_parquet({_path_list_sql(source.paths)}, union_by_name=true)"
    elif source.source_format == "csv":
        reader = f"read_csv_auto({_path_list_sql(source.paths)}, union_by_name=true, header=true)"
    else:
        raise ValueError(f"Unsupported snapshot format: {source.source_format}")
    connection.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM {reader}")


def _manifest_row(connection, source: SnapshotSource) -> dict[str, object]:
    table = _quote_ident(source.table_name)
    timestamp_column = TIMESTAMP_COLUMN_OVERRIDES.get(source.table_name)
    row_count = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    min_ts = None
    max_ts = None
    pre_1970_rows = 0
    if timestamp_column and _column_exists(connection, source.table_name, timestamp_column):
        column = _quote_ident(timestamp_column)
        utc_ts = f"(try_cast({column} AS TIMESTAMPTZ) AT TIME ZONE 'UTC')"
        min_ts, max_ts, pre_1970_rows = connection.execute(
            f"""
            SELECT
              min({utc_ts}),
              max({utc_ts}),
              sum(CASE
                    WHEN {utc_ts} < TIMESTAMP '1970-01-01 00:00:00'
                    THEN 1 ELSE 0
                  END)
            FROM {table}
            """
        ).fetchone()
    return {
        "table_name": source.table_name,
        "source_format": source.source_format,
        "source_path": source.source_path,
        "file_count": len(source.paths),
        "row_count": int(row_count or 0),
        "timestamp_column": timestamp_column,
        "min_ts": min_ts,
        "max_ts": max_ts,
        "pre_1970_rows": int(pre_1970_rows or 0),
        "includes_pre_1970": bool(pre_1970_rows and pre_1970_rows > 0),
    }


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"DESCRIBE {_quote_ident(table_name)}").fetchall()
    return column_name in {row[0] for row in rows}


def _manifest_columns() -> list[str]:
    return [
        "table_name",
        "source_format",
        "source_path",
        "file_count",
        "row_count",
        "timestamp_column",
        "min_ts",
        "max_ts",
        "pre_1970_rows",
        "includes_pre_1970",
    ]


def _path_list_sql(paths: tuple[Path, ...]) -> str:
    if len(paths) == 1:
        return _quote_string(paths[0])
    return "[" + ", ".join(_quote_string(path) for path in paths) + "]"


def _quote_string(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
