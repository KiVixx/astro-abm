from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from astro_abm.storage.questdb import QuestDBMarketBarWriter


MIGRATION_DIR = Path(__file__).resolve().parents[2] / "migrations"


TABLE_COLUMNS = {
    "astro_aspect_events": [
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
    ],
    "astro_moon_phase_events": [
        "exact_ts",
        "dataset_id",
        "event_id",
        "phase_name",
        "elongation_deg",
        "calc_version",
        "source_note",
    ],
    "astro_daily_positions": [
        "ts",
        "dataset_id",
        "body",
        "lon_deg",
        "lat_deg",
        "distance_au",
        "lon_speed_deg_day",
        "lat_speed_deg_day",
        "distance_speed_au_day",
        "right_ascension_deg",
        "declination_deg",
        "zodiac_sign",
        "zodiac_degree",
        "is_retrograde",
        "is_oob",
        "ephemeris_backend",
        "calc_version",
        "source_note",
    ],
    "astro_daily_facts": [
        "ts",
        "dataset_id",
        "body",
        "metric",
        "metric_group",
        "value_double",
        "value_long",
        "value_bool",
        "value_symbol",
        "value_text",
        "unit",
        "ephemeris_backend",
        "calc_version",
        "source_note",
    ],
    "astro_retrograde_cycles": [
        "station_in_ts",
        "dataset_id",
        "cycle_id",
        "body",
        "station_in_date_ts",
        "station_out_ts",
        "station_out_date_ts",
        "retrograde_start_ts",
        "retrograde_end_ts",
        "pre_window_start_ts",
        "post_window_end_ts",
        "retrograde_days",
        "pre_post_window_days",
        "station_phase_days",
        "station_in_type",
        "station_out_type",
        "calc_version",
        "source_note",
    ],
    "astro_event_windows": [
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
    ],
}

FEATURE_COLUMNS = [
    "ts",
    "dataset_id",
    "mercury_phase",
    "mercury_is_retrograde",
    "mercury_days_since_station",
    "mercury_days_until_station",
    "mercury_cycle_id",
    "venus_phase",
    "venus_is_retrograde",
    "venus_days_since_station",
    "venus_days_until_station",
    "venus_cycle_id",
    "mars_phase",
    "mars_is_retrograde",
    "mars_days_since_station",
    "mars_days_until_station",
    "mars_cycle_id",
    "jupiter_phase",
    "jupiter_is_retrograde",
    "jupiter_days_since_station",
    "jupiter_days_until_station",
    "jupiter_cycle_id",
    "saturn_phase",
    "saturn_is_retrograde",
    "saturn_days_since_station",
    "saturn_days_until_station",
    "saturn_cycle_id",
    "active_retrograde_count",
    "active_retrograde_bodies",
    "station_cluster_count_3d",
    "station_cluster_count_7d",
    "station_cluster_count_14d",
    "major_aspect_active_count",
    "major_aspect_cluster_count_3d",
    "major_aspect_cluster_count_7d",
    "major_aspect_cluster_count_14d",
    "moon_phase_name",
    "moon_phase_angle_deg",
    "moon_illumination_pct",
    "jupiter_saturn_angle_deg",
    "jupiter_saturn_regime",
    "mars_saturn_angle_deg",
    "mars_saturn_regime",
    "calc_version",
]
TABLE_COLUMNS["astro_daily_features"] = FEATURE_COLUMNS
TABLE_COLUMNS["market_daily_bars"] = [
    "ts",
    "asset",
    "source",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "currency",
    "market_timezone",
    "data_version",
    "source_note",
]
TABLE_COLUMNS["market_daily_features"] = [
    "ts",
    "asset",
    "source",
    "ret_1d",
    "log_ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "realized_vol_5d",
    "realized_vol_20d",
    "realized_vol_60d",
    "drawdown_5d",
    "drawdown_20d",
    "drawdown_60d",
    "abs_ret_rank_252d",
    "is_extreme_absret_95",
    "is_extreme_absret_99",
    "data_version",
]
TABLE_COLUMNS["event_study_results"] = [
    "ts",
    "run_id",
    "event_type",
    "asset",
    "window_name",
    "metric",
    "effect_value",
    "baseline_value",
    "effect_minus_baseline",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "p_value",
    "q_value_fdr",
    "n_events",
    "n_observations",
    "data_version",
    "calc_version",
    "source_note",
]
TABLE_COLUMNS["data_source_registry"] = [
    "ts",
    "source",
    "provider",
    "series_id",
    "asset",
    "frequency",
    "coverage_start_ts",
    "coverage_end_ts",
    "is_canonical",
    "requires_api_key",
    "license_note",
    "source_url",
    "data_version",
    "created_at",
]
TABLE_COLUMNS["macro_daily_observations"] = [
    "ts",
    "series_id",
    "source",
    "value",
    "original_frequency",
    "fill_method",
    "units",
    "data_version",
    "source_note",
]
TABLE_COLUMNS["market_asset_coverage"] = [
    "ts",
    "asset",
    "source",
    "coverage_start_ts",
    "coverage_end_ts",
    "observation_count",
    "missing_count",
    "missing_pct",
    "first_valid_ts",
    "last_valid_ts",
    "frequency",
    "data_version",
    "source_note",
]
TABLE_COLUMNS["financial_stress_daily"] = [
    "ts",
    "stress_universe",
    "equity_stress_score",
    "vol_stress_score",
    "rates_stress_score",
    "credit_stress_score",
    "dollar_stress_score",
    "gold_stress_score",
    "crypto_stress_score",
    "cross_asset_stress_score",
    "component_count",
    "spx_drawdown_20d",
    "spx_drawdown_60d",
    "spx_realized_vol_20d",
    "spx_absret_percentile_252d",
    "vix_level",
    "vix_percentile_252d",
    "vix_change_5d",
    "us10y_change_5d",
    "us10y_change_20d",
    "yield_curve_10y2y",
    "hy_oas_level",
    "hy_oas_change_20d",
    "nfci_level",
    "btc_drawdown_20d",
    "btc_realized_vol_20d",
    "gold_return_20d",
    "is_equity_stress",
    "is_vol_stress",
    "is_rates_stress",
    "is_credit_stress",
    "is_gold_stress",
    "is_crypto_stress",
    "is_cross_asset_stress",
    "stress_regime",
    "data_version",
]
TABLE_COLUMNS["research_events"] = [
    "event_ts",
    "event_id",
    "event_family",
    "event_type",
    "source_table",
    "source_event_id",
    "body",
    "body_a",
    "body_b",
    "aspect_name",
    "phase_name",
    "profile",
    "exact_ts",
    "event_date_ts",
    "event_strength",
    "cluster_count",
    "is_primary",
    "is_overlapping",
    "eligible_for_event_study",
    "exclusion_reason",
    "dataset_id",
    "calc_version",
]
TABLE_COLUMNS["research_hypotheses"] = [
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
TABLE_COLUMNS["event_study_runs"] = [
    "ts",
    "run_id",
    "hypothesis_id",
    "run_type",
    "event_family",
    "config_hash",
    "git_commit",
    "data_version",
    "astro_dataset_id",
    "start_ts",
    "end_ts",
    "assets",
    "metrics",
    "windows",
    "baseline_methods",
    "status",
    "warning_count",
    "report_path",
    "source_note",
]
TABLE_COLUMNS["event_study_results_v2"] = [
    "ts",
    "run_id",
    "hypothesis_id",
    "event_family",
    "event_type",
    "asset",
    "window_name",
    "baseline_method",
    "metric",
    "effect_value",
    "baseline_value",
    "effect_minus_baseline",
    "effect_ratio",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "p_value",
    "q_value_fdr",
    "placebo_percentile",
    "expected_direction",
    "effect_direction",
    "effect_direction_match",
    "n_events",
    "n_observations",
    "n_baseline_observations",
    "sample_warning",
    "overlap_warning",
    "coverage_warning",
    "data_version",
    "calc_version",
    "source_note",
]
TABLE_COLUMNS["world_event_catalog"] = [
    "start_ts",
    "event_id",
    "event_name",
    "category",
    "region",
    "country",
    "end_ts",
    "severity_score",
    "date_confidence",
    "source",
    "source_url",
    "notes",
    "data_version",
]


def apply_migrations(*, connection_factory=None, migration_dir: Path = MIGRATION_DIR) -> None:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    statements = []
    for path in sorted(migration_dir.glob("*.sql")):
        statements.extend(_split_sql(path.read_text()))
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        connection.commit()


def ingest_csv_snapshot(snapshot_dir: str | Path, *, tables: Iterable[str] | None = None, connection_factory=None, batch_size: int = 1000) -> dict[str, int]:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    snapshot = Path(snapshot_dir)
    selected_tables = tuple(tables or TABLE_COLUMNS.keys())
    counts: dict[str, int] = {}
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            for table in selected_tables:
                path = snapshot / f"{table}.csv"
                if not path.exists():
                    continue
                frame = pd.read_csv(path)
                columns = TABLE_COLUMNS[table]
                frame = frame.reindex(columns=columns)
                rows = [tuple(_null_to_none(value) for value in row) for row in frame.itertuples(index=False, name=None)]
                if not rows:
                    counts[table] = 0
                    continue
                placeholders = ", ".join(["%s"] * len(columns))
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                for index in range(0, len(rows), batch_size):
                    cursor.executemany(sql, rows[index : index + batch_size])
                counts[table] = len(rows)
        connection.commit()
    return counts


def _split_sql(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _null_to_none(value):
    if pd.isna(value):
        return None
    return value
