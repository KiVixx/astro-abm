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


class FakeCalculator:
    def compute_features(self, ts):
        return {
            "moon_phase_pct": 42.0,
            "moon_is_waxing": True,
        }


class FakeCursor:
    def __init__(self, existing_rows):
        self.existing_rows = existing_rows

    def execute(self, sql, params):
        return None

    def fetchall(self):
        return self.existing_rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, existing_rows=()):
        self.existing_rows = existing_rows

    def cursor(self):
        return FakeCursor(self.existing_rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_run_ephemeris_backfill_writes_global_hourly_rows_and_run_log():
    from astro_abm.etl.backfill_ephemeris import run_ephemeris_backfill

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_ephemeris_backfill(
        start_utc=datetime(2024, 4, 15, 13, 30, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 16, 0, tzinfo=UTC),
        calculator=FakeCalculator(),
        writer=fact_writer,
        run_writer=run_writer,
        connection_factory=lambda: FakeConnection(),
        run_id="ephemeris-test",
    )

    rows = fact_writer.batches[0]

    assert result.hours_seen == 3
    assert result.written == 6
    assert result.skipped_existing == 0
    assert result.errors == ()
    assert rows[0]["ts"] == datetime(2024, 4, 15, 13, tzinfo=UTC)
    assert rows[0]["entity_id"] == "GLOBAL"
    assert rows[0]["source"] == "pyswisseph"
    assert rows[0]["ingest_run_id"] == "ephemeris-test"
    assert run_writer.records[0].job_type == "ephemeris_backfill"
    assert run_writer.records[0].rows_written == 6


def test_run_ephemeris_backfill_skips_existing_hours():
    from astro_abm.etl.backfill_ephemeris import run_ephemeris_backfill

    existing = [(datetime(2024, 4, 15, 14, tzinfo=UTC),)]
    fact_writer = RecordingFactWriter()
    result = run_ephemeris_backfill(
        start_utc=datetime(2024, 4, 15, 13, 0, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 16, 0, tzinfo=UTC),
        calculator=FakeCalculator(),
        writer=fact_writer,
        run_writer=RecordingRunWriter(),
        connection_factory=lambda: FakeConnection(existing),
        record_run=False,
    )

    rows = fact_writer.batches[0]

    assert result.hours_seen == 3
    assert result.written == 4
    assert result.skipped_existing == 1
    assert {row["ts"] for row in rows} == {
        datetime(2024, 4, 15, 13, tzinfo=UTC),
        datetime(2024, 4, 15, 15, tzinfo=UTC),
    }
