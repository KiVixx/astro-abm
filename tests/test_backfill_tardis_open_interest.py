from datetime import UTC, date, datetime
from pathlib import Path


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


def test_run_tardis_open_interest_backfill_writes_hourly_vendor_rows(tmp_path):
    import gzip

    from astro_abm.etl.backfill_tardis_open_interest import run_tardis_open_interest_backfill

    csv_path = tmp_path / "BTCUSDT.csv.gz"
    with gzip.open(csv_path, "wt", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    "exchange,symbol,timestamp,local_timestamp,funding_timestamp,funding_rate,predicted_funding_rate,open_interest,last_price,index_price,mark_price",
                    "binance-futures,BTCUSDT,1580515200000000,1580515200000000,,,,100.0,9364.51,,9000.0",
                    "binance-futures,BTCUSDT,1580518800000000,1580518800000000,,,,110.0,9364.51,,9100.0",
                ]
            )
        )

    class FakeClient:
        def download_daily_derivative_ticker_csv(self, *, exchange, symbol, day, cache_dir):
            assert exchange == "binance-futures"
            assert symbol == "BTCUSDT"
            assert day == date(2020, 2, 1)
            assert isinstance(cache_dir, Path)
            return csv_path

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_tardis_open_interest_backfill(
        symbols=("BTCUSDT",),
        start_utc=datetime(2020, 2, 1, 0, tzinfo=UTC),
        end_utc=datetime(2020, 2, 1, 2, tzinfo=UTC),
        client=FakeClient(),
        writer=fact_writer,
        run_writer=run_writer,
        cache_dir=tmp_path,
        run_id="tardis-test",
    )

    assert result.days_seen == 1
    assert result.fetched_files == 1
    assert result.records_seen == 2
    assert result.written == 4
    assert {row["metric_name"] for row in fact_writer.rows} == {"open_interest", "open_interest_value"}
    assert fact_writer.rows[0]["source"] == "tardis_binance_futures"
    assert fact_writer.rows[0]["quality_flag"] == "vendor"
    assert fact_writer.rows[0]["ingest_run_id"] == "tardis-test"
    assert run_writer.records[0].provider == "tardis_binance_futures"
