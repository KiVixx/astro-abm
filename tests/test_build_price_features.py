from datetime import UTC, datetime


def test_run_price_feature_build_records_etl_run():
    from astro_abm.etl.build_price_features import run_price_feature_build

    queries = []

    class FakeCursor:
        def execute(self, sql, params=None):
            queries.append((sql, params))

        def fetchall(self):
            sql = queries[-1][0]
            if "FROM market_ohlcv_1h" in sql:
                return [
                    (datetime(2024, 4, 15, 0, tzinfo=UTC), "BTCUSDT", 100.0, 110.0, 95.0, 105.0, 10.0, "spot"),
                    (datetime(2024, 4, 15, 1, tzinfo=UTC), "BTCUSDT", 105.0, 108.0, 90.0, 95.0, 30.0, "spot"),
                    (datetime(2024, 4, 15, 2, tzinfo=UTC), "BTCUSDT", 95.0, 100.0, 94.0, 98.0, 20.0, "spot"),
                ]
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

    class RecordingWriter:
        def __init__(self):
            self.rows = []

        def write(self, rows):
            self.rows.extend(rows)

    class RecordingRunWriter:
        def __init__(self):
            self.records = []

        def write(self, record):
            self.records.append(record)

    writer = RecordingWriter()
    run_writer = RecordingRunWriter()

    result = run_price_feature_build(
        symbols=("BTCUSDT",),
        start_utc=datetime(2024, 4, 15, 0, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 3, tzinfo=UTC),
        connection_factory=lambda: FakeConnection(),
        writer=writer,
        run_writer=run_writer,
        run_id="price-test",
    )

    assert result.read_bars == 3
    assert result.written > 0
    assert result.errors == ()
    assert writer.rows[0]["ingest_run_id"] == "price-test"
    assert run_writer.records[0].job_type == "price_feature_build"
    assert run_writer.records[0].provider == "price_action"
