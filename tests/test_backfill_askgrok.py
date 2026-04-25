from datetime import UTC, datetime


class RecordingFactWriter:
    def __init__(self):
        self.batches = []

    def write(self, rows):
        self.batches.append(list(rows))


class RecordingRunWriter:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)


def test_run_askgrok_backfill_writes_hourly_rows_and_run_log():
    from astro_abm.etl.backfill_askgrok import run_askgrok_backfill

    calls = []

    class FakeClient:
        def fetch_feature_rows(self, start_utc, end_utc, assets):
            calls.append((start_utc, end_utc, assets))
            return [
                {
                    "ts": start_utc,
                    "entity_type": "social_sentiment",
                    "entity_id": ",".join(assets),
                    "source": "ASKGROK_WEB",
                    "interval": "1h",
                    "asset_class": "crypto",
                    "metric_name": "askgrok_sentiment_score",
                    "metric_value": -0.25,
                    "observed_ts": end_utc,
                    "available_ts": end_utc,
                }
            ]

    class FakeCursor:
        def execute(self, sql, params):
            self.result = (0,)

        def fetchone(self):
            return self.result

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

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()

    result = run_askgrok_backfill(
        start_utc=datetime(2024, 4, 15, 13, 20, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 16, 0, tzinfo=UTC),
        assets=("btc", "eth"),
        max_hours=2,
        client=FakeClient(),
        fact_writer=fact_writer,
        run_writer=run_writer,
        connection_factory=lambda: FakeConnection(),
    )

    assert result.status == "success"
    assert result.attempted_hours == 2
    assert result.rows_written == 2
    assert result.window_start == datetime(2024, 4, 15, 13, 0, tzinfo=UTC)
    assert result.window_end == datetime(2024, 4, 15, 15, 0, tzinfo=UTC)
    assert calls[0] == (
        datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
        datetime(2024, 4, 15, 14, 0, tzinfo=UTC),
        ["BTC", "ETH"],
    )
    assert fact_writer.batches[0][0]["ingest_run_id"] == result.run_id
    assert run_writer.records[0].run_id == result.run_id
    assert run_writer.records[0].rows_written == 2


def test_run_askgrok_backfill_skips_existing_hour():
    from astro_abm.etl.backfill_askgrok import run_askgrok_backfill

    class FakeClient:
        def fetch_feature_rows(self, **kwargs):
            raise AssertionError("existing rows should be skipped before fetching")

    class FakeCursor:
        def execute(self, sql, params):
            self.result = (1,)

        def fetchone(self):
            return self.result

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

    result = run_askgrok_backfill(
        start_utc=datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 14, 0, tzinfo=UTC),
        assets=("BTC",),
        client=FakeClient(),
        fact_writer=RecordingFactWriter(),
        run_writer=RecordingRunWriter(),
        connection_factory=lambda: FakeConnection(),
    )

    assert result.status == "success"
    assert result.rows_written == 0
    assert result.skipped_existing == 1
