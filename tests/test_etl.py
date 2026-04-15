from datetime import UTC, datetime

import pandas as pd


def test_normalize_to_utc_hour_converts_timezone_and_floors_to_hour():
    from astro_abm.etl.pipeline import normalize_to_utc_hour

    ts = normalize_to_utc_hour("2024-04-15T11:37:12-04:00")

    assert ts == datetime(2024, 4, 15, 15, 0, tzinfo=UTC)


def test_align_tradfi_hourly_forward_fills_missing_hours():
    from astro_abm.etl.pipeline import align_tradfi_hourly

    frame = pd.DataFrame(
        [
            {"ts": "2024-04-15T13:00:00Z", "symbol": "SPY", "close": 510.0},
            {"ts": "2024-04-15T15:00:00Z", "symbol": "SPY", "close": 512.0},
        ]
    )

    aligned = align_tradfi_hourly(frame, symbol="SPY")

    assert list(aligned["ts"]) == [
        datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
        datetime(2024, 4, 15, 14, 0, tzinfo=UTC),
        datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
    ]
    assert list(aligned["close"]) == [510.0, 510.0, 512.0]
    assert list(aligned["symbol"]) == ["SPY", "SPY", "SPY"]


def test_merge_hourly_frames_joins_market_and_feature_columns_on_ts():
    from astro_abm.etl.pipeline import merge_hourly_frames

    market = pd.DataFrame(
        [
            {"ts": datetime(2024, 4, 15, 13, 0, tzinfo=UTC), "symbol": "BTC", "close": 65000.0},
            {"ts": datetime(2024, 4, 15, 14, 0, tzinfo=UTC), "symbol": "BTC", "close": 65100.0},
        ]
    )
    features = pd.DataFrame(
        [
            {"ts": datetime(2024, 4, 15, 13, 0, tzinfo=UTC), "kp_index": 4.0},
            {"ts": datetime(2024, 4, 15, 14, 0, tzinfo=UTC), "kp_index": 5.0},
        ]
    )

    merged = merge_hourly_frames([market, features], on=["ts"])

    assert list(merged.columns) == ["ts", "symbol", "close", "kp_index"]
    assert merged.iloc[0]["kp_index"] == 4.0
    assert merged.iloc[1]["close"] == 65100.0


def test_dataframe_to_hourly_fact_rows_shapes_records_for_unified_writer():
    from astro_abm.etl.pipeline import dataframe_to_hourly_fact_rows

    frame = pd.DataFrame(
        [
            {
                "ts": datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
                "entity_type": "space_weather",
                "entity_id": "GLOBAL",
                "source": "noaa_swpc",
                "interval": "1h",
                "asset_class": "macro",
                "metric_name": "kp_index",
                "metric_value": 4.0,
                "observed_ts": datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
                "available_ts": datetime(2024, 4, 15, 13, 5, tzinfo=UTC),
            }
        ]
    )

    rows = dataframe_to_hourly_fact_rows(frame)

    assert rows == [
        (
            datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
            "space_weather",
            "GLOBAL",
            "noaa_swpc",
            "1h",
            "macro",
            None,
            None,
            "kp_index",
            4.0,
            None,
            None,
            None,
            datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
            datetime(2024, 4, 15, 13, 5, tzinfo=UTC),
            None,
            None,
            None,
        )
    ]


def test_build_scheduler_wires_hourly_job_at_minute_five_utc():
    from astro_abm.etl.scheduler import build_scheduler

    scheduler = build_scheduler(job_func=lambda: None, timezone="UTC")
    job = scheduler.get_job("hourly_etl")

    assert job is not None
    assert job.max_instances == 1
    assert job.coalesce is True
    assert job.misfire_grace_time == 900
    assert str(job.trigger.timezone) == "UTC"
    assert "minute='5'" in str(job.trigger)
