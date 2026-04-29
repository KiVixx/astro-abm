from datetime import UTC, datetime
from io import StringIO


def test_parse_binance_vision_metrics_csv_deduplicates_timestamp_rows():
    from astro_abm.market_data.binance_vision_metrics import parse_binance_vision_metrics_csv

    records = parse_binance_vision_metrics_csv(
        StringIO(
            "\n".join(
                [
                    "create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio",
                    "2020-09-01 00:00:00,BTCUSDT,39080.231,456144339.23,1.17,1.23,1.35,0.78",
                    "2020-09-01 00:00:00,BTCUSDT,39081.000,456144400.00,1.18,1.24,1.36,0.79",
                    "2020-09-01 00:05:00,BTCUSDT,39106.413,455693833.60,1.19,1.25,1.37,0.80",
                ]
            )
        )
    )

    assert len(records) == 2
    assert records[0].ts == datetime(2020, 9, 1, 0, 0, tzinfo=UTC)
    assert records[0].open_interest == 39081.0
    assert records[1].open_interest_value == 455693833.60


def test_aggregate_binance_vision_metrics_hourly_uses_last_5m_snapshot():
    from astro_abm.market_data.binance_vision_metrics import (
        BinanceVisionMetricRecord,
        aggregate_binance_vision_metrics_hourly,
    )

    hourly = aggregate_binance_vision_metrics_hourly(
        [
            BinanceVisionMetricRecord(datetime(2020, 9, 1, 0, 5, tzinfo=UTC), "BTCUSDT", 100.0, 1000.0, 1, 2, 3, 4),
            BinanceVisionMetricRecord(datetime(2020, 9, 1, 0, 55, tzinfo=UTC), "BTCUSDT", 110.0, 1100.0, 2, 3, 4, 5),
            BinanceVisionMetricRecord(datetime(2020, 9, 1, 1, 5, tzinfo=UTC), "BTCUSDT", 120.0, 1200.0, 3, 4, 5, 6),
        ]
    )

    assert [record.ts for record in hourly] == [
        datetime(2020, 9, 1, 0, tzinfo=UTC),
        datetime(2020, 9, 1, 1, tzinfo=UTC),
    ]
    assert hourly[0].open_interest == 110.0
    assert hourly[0].sum_taker_long_short_vol_ratio == 5


def test_build_binance_vision_metric_feature_rows_shapes_official_rows():
    from astro_abm.market_data.binance_vision_metrics import BinanceVisionMetricRecord, build_binance_vision_metric_feature_rows

    rows = build_binance_vision_metric_feature_rows(
        [
            BinanceVisionMetricRecord(
                datetime(2020, 9, 1, 0, tzinfo=UTC),
                "BTCUSDT",
                100.0,
                1000.0,
                1.1,
                1.2,
                1.3,
                1.4,
            )
        ]
    )
    by_metric = {row["metric_name"]: row for row in rows}

    assert by_metric["open_interest"]["source"] == "binance_vision_metrics"
    assert by_metric["open_interest"]["quality_flag"] == "official"
    assert by_metric["open_interest"]["metric_value"] == 100.0
    assert by_metric["sum_taker_long_short_vol_ratio"]["metric_value"] == 1.4
