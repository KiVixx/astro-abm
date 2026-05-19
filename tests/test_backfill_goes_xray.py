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
    def __init__(self, path):
        self.path = path
        self.calls = []

    def download_year(self, *, year, satellite, cache_dir):
        self.calls.append((year, satellite, cache_dir))
        return self.path


class UnavailableClient:
    def __init__(self):
        self.download_calls = []
        self.healthcheck_calls = 0

    def is_year_cached(self, *, year, satellite, cache_dir):
        return False

    def archive_healthcheck(self):
        self.healthcheck_calls += 1
        return False, "ConnectTimeout:archive unavailable"

    def download_year(self, *, year, satellite, cache_dir):
        self.download_calls.append((year, satellite, cache_dir))
        raise AssertionError("download should be skipped when archive healthcheck fails")


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


def test_run_goes_xray_backfill_writes_rows_and_run_log(tmp_path):
    import h5py
    import numpy as np

    from astro_abm.etl.backfill_goes_xray import run_goes_xray_backfill
    from astro_abm.features.goes_xray import GOES_XRS_EPOCH

    path = tmp_path / "sample.nc"
    ts = datetime(2024, 4, 15, 9, 5, tzinfo=UTC)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("time", data=np.array([(ts - GOES_XRS_EPOCH).total_seconds()]))
        handle.create_dataset("xrsb_flux", data=np.array([2.0e-7], dtype="float32"))

    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_goes_xray_backfill(
        start_utc=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 10, tzinfo=UTC),
        client=FakeClient(path),
        writer=fact_writer,
        run_writer=run_writer,
        connection_factory=lambda: FakeConnection(),
        cache_dir=tmp_path,
        run_id="goes-xray-test",
    )

    assert result.years_seen == 1
    assert result.records_seen == 1
    assert result.written == 1
    assert result.errors == ()
    assert fact_writer.batches[0][0]["ingest_run_id"] == "goes-xray-test"
    assert run_writer.records[0].provider == "noaa_goes_xrs"
    assert run_writer.records[0].rows_written == 1


def test_run_goes_xray_backfill_skips_uncached_year_when_archive_unavailable(tmp_path):
    from astro_abm.etl.backfill_goes_xray import run_goes_xray_backfill

    client = UnavailableClient()
    fact_writer = RecordingFactWriter()
    run_writer = RecordingRunWriter()
    result = run_goes_xray_backfill(
        start_utc=datetime(2026, 5, 1, tzinfo=UTC),
        end_utc=datetime(2026, 5, 2, tzinfo=UTC),
        client=client,
        writer=fact_writer,
        run_writer=run_writer,
        connection_factory=lambda: FakeConnection(),
        cache_dir=tmp_path,
        run_id="goes-xray-unavailable-test",
    )

    assert result.years_seen == 1
    assert result.records_seen == 0
    assert result.written == 0
    assert result.skipped_existing == 0
    assert result.errors == ("2026:g18:SourceUnavailable:ConnectTimeout:archive unavailable",)
    assert client.healthcheck_calls == 1
    assert client.download_calls == []
    assert fact_writer.batches == []
    assert run_writer.records[0].status == "failed"
    assert run_writer.records[0].errors == 1
