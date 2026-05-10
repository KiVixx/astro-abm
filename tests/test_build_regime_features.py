from datetime import UTC, datetime, timedelta


class FakeConnection:
    def __init__(self, queries):
        self.queries = queries

    def cursor(self):
        return FakeCursor(self.queries)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeCursor:
    def __init__(self, queries):
        self.queries = queries

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchall(self):
        sql = self.queries[-1][0]
        start = datetime(2024, 1, 1, tzinfo=UTC)
        if "FROM v_market_ohlcv_ml_1h" in sql:
            return [
                (start + timedelta(hours=index), "BTCUSDT", 100.0 + index, 10.0, "official", False)
                for index in range(220)
            ]
        if "FROM v_open_interest_unified" in sql:
            return [(start + timedelta(hours=index), "BTCUSDT", 1000.0 + index * 5) for index in range(220)]
        if "metric_name = 'funding_rate'" in sql:
            return [(start + timedelta(hours=index), "BTCUSDT", 0.0001 + index * 0.000001) for index in range(220)]
        return []

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


def test_run_regime_feature_build_writes_rows_and_run_log():
    from astro_abm.etl.build_regime_features import run_regime_feature_build

    queries = []
    writer = RecordingWriter()
    run_writer = RecordingRunWriter()

    result = run_regime_feature_build(
        symbols=("BTCUSDT",),
        start_utc=datetime(2024, 1, 8, tzinfo=UTC),
        end_utc=datetime(2024, 1, 9, tzinfo=UTC),
        connection_factory=lambda: FakeConnection(queries),
        writer=writer,
        run_writer=run_writer,
        run_id="regime-test",
    )

    assert result.written > 0
    assert result.errors == ()
    assert any(row["metric_name"] == "regime_leverage_pressure" for row in writer.rows)
    assert writer.rows[0]["ingest_run_id"] == "regime-test"
    assert run_writer.records[0].job_type == "regime_feature_build"
    assert run_writer.records[0].provider == "regime_features"
    assert any("v_market_ohlcv_ml_1h" in sql for sql, _params in queries)
    assert any("v_open_interest_unified" in sql for sql, _params in queries)
