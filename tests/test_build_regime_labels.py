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
                for index in range(80)
            ]
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


def test_run_regime_label_build_writes_rows_and_run_log():
    from astro_abm.etl.build_regime_labels import run_regime_label_build

    queries = []
    writer = RecordingWriter()
    run_writer = RecordingRunWriter()

    result = run_regime_label_build(
        symbols=("BTCUSDT",),
        start_utc=datetime(2024, 1, 2, tzinfo=UTC),
        end_utc=datetime(2024, 1, 3, tzinfo=UTC),
        connection_factory=lambda: FakeConnection(queries),
        writer=writer,
        run_writer=run_writer,
        run_id="labels-test",
    )

    assert result.written > 0
    assert result.errors == ()
    assert any(row["metric_name"] == "future_realized_vol_24h" for row in writer.rows)
    assert writer.rows[0]["ingest_run_id"] == "labels-test"
    assert run_writer.records[0].job_type == "regime_label_build"
    assert run_writer.records[0].provider == "regime_labels"
    assert any("v_market_ohlcv_ml_1h" in sql for sql, _params in queries)
