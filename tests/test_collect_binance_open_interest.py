from datetime import UTC, datetime


class RecordingFactWriter:
    def __init__(self):
        self.rows = []
        self.connection_factory = lambda: FakeConnection()

    def write(self, rows):
        self.rows.extend(rows)


class RecordingRunWriter:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)


class FakeConnection:
    def cursor(self):
        return FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeCursor:
    def execute(self, sql, params):
        return None

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_run_binance_open_interest_collect_writes_hourly_rows_and_run_log():
    from astro_abm.etl.collect_binance_open_interest import run_binance_open_interest_collect

    class FakeClient:
        def fetch_current_open_interest(self, *, symbol):
            return {
                "symbol": symbol,
                "openInterest": "20403.637",
                "time": 1713171900000,
            }

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()

    result = run_binance_open_interest_collect(
        symbols=("btcusdt",),
        run_ts=datetime(2024, 4, 15, 9, 35, tzinfo=UTC),
        client=FakeClient(),
        writer=fact_writer,
        run_writer=run_writer,
        run_id="binance-current-test",
    )

    assert result.fetched == 1
    assert result.written == 1
    assert fact_writer.rows[0]["ts"] == datetime(2024, 4, 15, 9, tzinfo=UTC)
    assert fact_writer.rows[0]["source"] == "binance_futures_current"
    assert fact_writer.rows[0]["ingest_run_id"] == "binance-current-test"
    assert run_writer.records[0].provider == "binance_futures_current"
