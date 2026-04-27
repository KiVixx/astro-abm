from datetime import UTC, datetime


def test_parse_tardis_derivative_ticker_open_interest_skips_blank_values():
    from io import StringIO

    from astro_abm.market_data.tardis_derivatives import parse_tardis_derivative_ticker_open_interest_csv

    records = parse_tardis_derivative_ticker_open_interest_csv(
        StringIO(
            "\n".join(
                [
                    "exchange,symbol,timestamp,local_timestamp,funding_timestamp,funding_rate,predicted_funding_rate,open_interest,last_price,index_price,mark_price",
                    "binance-futures,BTCUSDT,1580515202348000,1580515202497335,,,,,9364.51,,",
                    "binance-futures,BTCUSDT,1580515500000000,1580515501000000,,,,100.5,9364.51,,9360.0",
                ]
            )
        ),
        symbol="BTCUSDT",
    )

    assert len(records) == 1
    assert records[0].ts == datetime(2020, 2, 1, 0, 5, tzinfo=UTC)
    assert records[0].open_interest == 100.5
    assert records[0].mark_price == 9360.0
    assert records[0].open_interest_value == 100.5 * 9360.0


def test_aggregate_open_interest_hourly_uses_last_value_in_each_hour():
    from astro_abm.market_data.tardis_derivatives import TardisOpenInterestRecord, aggregate_open_interest_hourly

    hourly = aggregate_open_interest_hourly(
        [
            TardisOpenInterestRecord(datetime(2020, 2, 1, 0, 5, tzinfo=UTC), "BTCUSDT", 100.0, 9000.0),
            TardisOpenInterestRecord(datetime(2020, 2, 1, 0, 55, tzinfo=UTC), "BTCUSDT", 110.0, 9100.0),
            TardisOpenInterestRecord(datetime(2020, 2, 1, 1, 5, tzinfo=UTC), "BTCUSDT", 120.0, None),
        ]
    )

    assert [record.ts for record in hourly] == [
        datetime(2020, 2, 1, 0, tzinfo=UTC),
        datetime(2020, 2, 1, 1, tzinfo=UTC),
    ]
    assert hourly[0].open_interest == 110.0
    assert hourly[0].mark_price == 9100.0
    assert hourly[1].open_interest == 120.0


def test_build_tardis_open_interest_feature_rows_shapes_vendor_rows():
    from astro_abm.market_data.tardis_derivatives import TardisOpenInterestRecord, build_tardis_open_interest_feature_rows

    rows = build_tardis_open_interest_feature_rows(
        [
            TardisOpenInterestRecord(
                datetime(2020, 2, 1, 0, tzinfo=UTC),
                "BTCUSDT",
                100.0,
                9000.0,
            )
        ]
    )

    by_metric = {row["metric_name"]: row for row in rows}

    assert by_metric["open_interest"]["source"] == "tardis_binance_futures"
    assert by_metric["open_interest"]["quality_flag"] == "vendor"
    assert by_metric["open_interest"]["metric_value"] == 100.0
    assert by_metric["open_interest_value"]["metric_value"] == 900000.0
