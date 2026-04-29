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


def test_run_binance_vision_metrics_backfill_writes_official_rows(tmp_path):
    import zipfile

    from astro_abm.etl.backfill_binance_vision_metrics import run_binance_vision_metrics_backfill

    zip_path = tmp_path / "BTCUSDT-metrics-2020-09-01.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "BTCUSDT-metrics-2020-09-01.csv",
            "\n".join(
                [
                    "create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio",
                    "2020-09-01 00:05:00,BTCUSDT,100.0,1000.0,1.1,1.2,1.3,1.4",
                    "2020-09-01 00:55:00,BTCUSDT,110.0,1100.0,1.2,1.3,1.4,1.5",
                ]
            ),
        )

    class FakeClient:
        def download_daily_metrics_zip(self, *, symbol, day, cache_dir):
            assert symbol == "BTCUSDT"
            assert day == date(2020, 9, 1)
            assert isinstance(cache_dir, Path)
            return zip_path

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_binance_vision_metrics_backfill(
        symbols=("BTCUSDT",),
        start_utc=datetime(2020, 9, 1, 0, tzinfo=UTC),
        end_utc=datetime(2020, 9, 1, 1, tzinfo=UTC),
        client=FakeClient(),
        writer=fact_writer,
        run_writer=run_writer,
        cache_dir=tmp_path,
        run_id="binance-vision-test",
    )

    assert result.days_seen == 1
    assert result.fetched_files == 1
    assert result.missing_files == 0
    assert result.records_seen == 2
    assert result.written == 6
    assert {row["metric_name"] for row in fact_writer.rows} == {
        "open_interest",
        "open_interest_value",
        "count_toptrader_long_short_ratio",
        "sum_toptrader_long_short_ratio",
        "count_long_short_ratio",
        "sum_taker_long_short_vol_ratio",
    }
    assert fact_writer.rows[0]["source"] == "binance_vision_metrics"
    assert fact_writer.rows[0]["ingest_run_id"] == "binance-vision-test"
    assert run_writer.records[0].provider == "binance_vision_metrics"


def test_run_binance_vision_metrics_backfill_treats_404_as_missing_file(tmp_path):
    import requests

    from astro_abm.etl.backfill_binance_vision_metrics import run_binance_vision_metrics_backfill

    class FakeClient:
        def download_daily_metrics_zip(self, **kwargs):
            response = requests.Response()
            response.status_code = 404
            raise requests.HTTPError("not found", response=response)

    result = run_binance_vision_metrics_backfill(
        symbols=("BTCUSDT",),
        start_utc=datetime(2020, 9, 1, 0, tzinfo=UTC),
        end_utc=datetime(2020, 9, 2, 0, tzinfo=UTC),
        client=FakeClient(),
        writer=RecordingFactWriter(),
        run_writer=RecordingRunWriter(),
        cache_dir=tmp_path,
    )

    assert result.days_seen == 1
    assert result.fetched_files == 0
    assert result.missing_files == 1
    assert result.errors == ()
