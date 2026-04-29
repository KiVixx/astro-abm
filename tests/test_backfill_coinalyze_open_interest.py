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


def test_run_coinalyze_open_interest_backfill_writes_vendor_rows():
    from astro_abm.etl.backfill_coinalyze_open_interest import run_coinalyze_open_interest_backfill

    class FakeClient:
        def fetch_open_interest_history(self, **kwargs):
            return [
                {
                    "symbol": "BTCUSDT_PERP.A",
                    "history": [{"t": 1713171600, "o": 100.0, "h": 120.0, "l": 90.0, "c": 110.0}],
                }
            ]

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_coinalyze_open_interest_backfill(
        symbols=("BTCUSDT_PERP.A",),
        start_utc=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 10, tzinfo=UTC),
        interval="1hour",
        client=FakeClient(),
        writer=fact_writer,
        run_writer=run_writer,
        run_id="coinalyze-test",
    )

    assert result.fetched_points == 1
    assert result.written == 1
    assert fact_writer.rows[0]["source"] == "coinalyze"
    assert fact_writer.rows[0]["quality_flag"] == "vendor"
    assert fact_writer.rows[0]["interval"] == "1h"
    assert fact_writer.rows[0]["ingest_run_id"] == "coinalyze-test"
    assert run_writer.records[0].provider == "coinalyze"
