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


class FakeClient:
    def fetch_year(self, year):
        return "\n".join(
            [
                _line(year, 106, 9, speed="421.4", bz="-3.2", kp="33"),
                _line(year, 106, 10, speed="425.0", bz="-2.0", kp="33"),
            ]
        )


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


def test_run_space_weather_backfill_writes_omni_rows_and_run_log():
    from astro_abm.etl.backfill_space_weather import run_space_weather_backfill

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_space_weather_backfill(
        start_utc=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 11, tzinfo=UTC),
        client=FakeClient(),
        writer=fact_writer,
        run_writer=run_writer,
        connection_factory=lambda: FakeConnection(),
        run_id="space-weather-test",
    )

    rows = fact_writer.batches[0]

    assert result.years_seen == 1
    assert result.records_seen == 2
    assert result.written == 6
    assert result.errors == ()
    assert {row["metric_name"] for row in rows} == {"solar_wind_speed", "imf_bz", "kp_index"}
    assert rows[0]["ingest_run_id"] == "space-weather-test"
    assert run_writer.records[0].job_type == "space_weather_backfill"
    assert run_writer.records[0].rows_written == 6


def test_run_space_weather_backfill_skips_existing_metric_timestamps():
    from astro_abm.etl.backfill_space_weather import run_space_weather_backfill

    existing = [(datetime(2024, 4, 15, 9, tzinfo=UTC),)]
    fact_writer = RecordingFactWriter()
    result = run_space_weather_backfill(
        start_utc=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 10, tzinfo=UTC),
        client=FakeClient(),
        writer=fact_writer,
        run_writer=RecordingRunWriter(),
        connection_factory=lambda: FakeConnection(existing),
        record_run=False,
    )

    assert result.written == 0
    assert result.skipped_existing == 3
    assert fact_writer.batches[0] == []


def _line(year, day, hour, *, speed, bz, kp):
    parts = [str(year), str(day), str(hour)] + ["0"] * 36
    parts[16] = bz
    parts[24] = speed
    parts[38] = kp
    return " ".join(parts)
