from datetime import UTC, datetime


def test_format_data_completeness_report_renders_coverage_sections():
    from astro_abm.analysis.data_completeness import format_data_completeness_report

    report = {
        "market_rows": [
            ("BTCUSDT", "binance", 100, datetime(2024, 4, 15, 0), datetime(2024, 4, 16, 0)),
        ],
        "space_weather_rows": [
            ("nasa_omni", "imf_bz", "authoritative", 24, datetime(2024, 4, 15, 0), datetime(2024, 4, 15, 23)),
            ("noaa_swpc_recent", "imf_bz", "provisional", 2, datetime(2024, 4, 16, 0), datetime(2024, 4, 16, 1)),
        ],
        "open_interest_rows": [
            ("tardis_binance_futures", "BTCUSDT", "open_interest", "vendor", 24, datetime(2024, 4, 15, 0), datetime(2024, 4, 15, 23)),
        ],
        "fact_rows": [
            ("price_action", "price_action", "BTCUSDT", "price_return_1h", "derived", 99, datetime(2024, 4, 15, 1), datetime(2024, 4, 16, 0)),
        ],
        "etl_runs": [
            (
                "space_weather_backfill",
                "nasa_omni",
                "success",
                24,
                0,
                0,
                datetime(2024, 4, 15, 0),
                datetime(2024, 4, 16, 0),
                datetime(2024, 4, 16, 1),
            )
        ],
    }

    text = format_data_completeness_report(report, as_of=datetime(2024, 4, 16, 2, tzinfo=UTC))

    assert "Data Completeness Report" in text
    assert "Market OHLCV" in text
    assert "BTCUSDT/binance: rows=100" in text
    assert "BTCUSDT/binance: rows=100 range=2024-04-15 00:00 -> 2024-04-16 00:00 lag=2.0h health=OK" in text
    assert "Unified Space Weather" in text
    assert "imf_bz [nasa_omni/authoritative]: rows=24" in text
    assert "imf_bz [noaa_swpc_recent/provisional]: rows=2" in text
    assert "Unified Open Interest" in text
    assert "BTCUSDT/open_interest [tardis_binance_futures/vendor]: rows=24" in text
    assert "Hourly Facts" in text
    assert "price_action/price_action/BTCUSDT/price_return_1h [derived]" in text
    assert "Recent ETL Runs" in text
    assert "space_weather_backfill/nasa_omni/success" in text


def test_format_data_completeness_report_marks_stale_rows():
    from astro_abm.analysis.data_completeness import format_data_completeness_report

    report = {
        "market_rows": [
            ("BTCUSDT", "binance", 100, datetime(2024, 4, 1, 0), datetime(2024, 4, 1, 0)),
        ],
        "space_weather_rows": [
            ("nasa_omni", "imf_bz", "authoritative", 24, datetime(2024, 3, 1, 0), datetime(2024, 3, 15, 0)),
        ],
        "open_interest_rows": [
            ("binance_vision_metrics", "BTCUSDT", "open_interest", "official", 24, datetime(2024, 4, 1, 0), datetime(2024, 4, 10, 0)),
        ],
        "fact_rows": [],
        "etl_runs": [],
    }

    text = format_data_completeness_report(report, as_of=datetime(2024, 4, 16, 2, tzinfo=UTC))

    assert "BTCUSDT/binance: rows=100" in text
    assert "lag=15.1d health=STALE" in text
    assert "imf_bz [nasa_omni/authoritative]" in text
    assert "health=OK" in text


def test_load_data_completeness_report_queries_expected_tables():
    from astro_abm.analysis.data_completeness import load_data_completeness_report

    executed = []

    class FakeCursor:
        def execute(self, sql, params=None):
            executed.append((sql, params))

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    report = load_data_completeness_report(recent_runs=5, connection_factory=lambda: FakeConnection())

    assert report == {
        "market_rows": [],
        "fact_rows": [],
        "space_weather_rows": [],
        "open_interest_rows": [],
        "etl_runs": [],
    }
    assert any("market_ohlcv_1h" in sql for sql, _params in executed)
    assert any("abm_hourly_facts" in sql for sql, _params in executed)
    assert any("v_space_weather_unified" in sql for sql, _params in executed)
    assert any("v_open_interest_unified" in sql for sql, _params in executed)
    assert executed[-1][1] == (5,)
