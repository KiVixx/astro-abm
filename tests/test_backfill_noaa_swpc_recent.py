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
    def fetch_plasma(self):
        return [{"time_tag": datetime(2026, 4, 15, 12, tzinfo=UTC), "speed": 421.4}]

    def fetch_magnetometer(self):
        return [{"time_tag": datetime(2026, 4, 15, 12, tzinfo=UTC), "bz_gsm": -3.2}]

    def fetch_xray_flux(self):
        return [{"time_tag": datetime(2026, 4, 15, 12, tzinfo=UTC), "flux": 2.2e-08}]

    def fetch_hourly_kp(self):
        return [{"ts": datetime(2026, 4, 15, 12, tzinfo=UTC), "kp_index": 4.67}]


class FakeCursor:
    def __init__(self, existing_rows=()):
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


def test_run_noaa_swpc_recent_backfill_writes_provisional_rows_and_run_log():
    from astro_abm.etl.backfill_noaa_swpc_recent import run_noaa_swpc_recent_backfill

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_noaa_swpc_recent_backfill(
        start_utc=datetime(2026, 4, 15, 12, tzinfo=UTC),
        end_utc=datetime(2026, 4, 15, 13, tzinfo=UTC),
        client=FakeClient(),
        writer=fact_writer,
        run_writer=run_writer,
        connection_factory=lambda: FakeConnection(),
        run_id="swpc-recent-test",
    )

    rows = fact_writer.batches[0]

    assert result.hours_seen == 1
    assert result.written == 4
    assert result.errors == ()
    assert {row["metric_name"] for row in rows} == {"solar_wind_speed", "imf_bz", "xray_flux", "kp_index"}
    assert rows[0]["source"] == "noaa_swpc_recent"
    assert rows[0]["quality_flag"] == "provisional"
    assert rows[0]["ingest_run_id"] == "swpc-recent-test"
    assert run_writer.records[0].provider == "noaa_swpc_recent"
