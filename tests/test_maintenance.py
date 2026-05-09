from datetime import UTC, datetime


def test_run_maintenance_tasks_continues_after_failure():
    from astro_abm.etl.maintenance import run_maintenance_tasks

    class Summary:
        written = 3
        skipped_existing = 2
        errors = ()
        fetched = 5
        run_id = "ok-run"

    def ok_task():
        return Summary()

    def bad_task():
        raise RuntimeError("boom")

    results = run_maintenance_tasks((("ok", ok_task), ("bad", bad_task)))

    assert results[0].name == "ok"
    assert results[0].status == "success"
    assert results[0].rows_written == 3
    assert "fetched=5" in results[0].details
    assert results[1].name == "bad"
    assert results[1].status == "failed"
    assert results[1].errors == ("RuntimeError:boom",)


def test_run_hourly_maintenance_wires_1h_tasks_without_social_sentiment(monkeypatch):
    from astro_abm.etl import maintain_hourly

    calls = []

    class Summary:
        def __init__(self, written=1):
            self.written = written
            self.skipped_existing = 0
            self.errors = ()

    def record(name):
        def inner(**kwargs):
            calls.append((name, kwargs))
            return Summary()

        return inner

    monkeypatch.setattr(maintain_hourly, "run_binance_spot_backfill", record("spot"))
    monkeypatch.setattr(maintain_hourly, "run_binance_derivatives_backfill", record("derivatives"))
    monkeypatch.setattr(maintain_hourly, "run_price_feature_build", record("price_action"))
    monkeypatch.setattr(maintain_hourly, "run_binance_open_interest_collect", record("current_oi"))
    monkeypatch.setattr(maintain_hourly, "run_noaa_swpc_recent_backfill", record("swpc"))
    monkeypatch.setattr(maintain_hourly, "run_ephemeris_backfill", record("ephemeris"))

    summary = maintain_hourly.run_hourly_maintenance(
        run_ts=datetime(2024, 4, 15, 10, 37, tzinfo=UTC),
        symbols=("btcusdt", "ethusdt"),
        lookback_hours=6,
    )

    assert summary.run_ts == datetime(2024, 4, 15, 10, tzinfo=UTC)
    assert [task.name for task in summary.tasks] == [
        "binance_spot_recent",
        "binance_derivatives_recent",
        "price_action_recent",
        "binance_current_open_interest",
        "noaa_swpc_recent",
        "ephemeris_current_hour",
    ]
    assert calls[0][1]["start_utc"] == datetime(2024, 4, 15, 4, tzinfo=UTC)
    assert calls[0][1]["end_utc"] == datetime(2024, 4, 15, 10, tzinfo=UTC)
    assert calls[2][1]["start_utc"] == datetime(2024, 4, 1, 10, tzinfo=UTC)
    assert calls[2][1]["end_utc"] == datetime(2024, 4, 15, 10, tzinfo=UTC)
    assert calls[3][1]["run_ts"] == datetime(2024, 4, 15, 10, tzinfo=UTC)
    assert all("social" not in name for name, _kwargs in calls)


def test_run_daily_maintenance_uses_archive_windows(monkeypatch):
    from astro_abm.etl import maintain_daily

    calls = []

    class Summary:
        written = 0
        skipped_existing = 1
        errors = ()

    def record(name):
        def inner(**kwargs):
            calls.append((name, kwargs))
            return Summary()

        return inner

    monkeypatch.setattr(maintain_daily, "run_binance_vision_metrics_backfill", record("vision"))
    monkeypatch.setattr(maintain_daily, "run_goes_xray_backfill", record("goes"))
    monkeypatch.setattr(maintain_daily, "run_noaa_swpc_recent_backfill", record("swpc"))
    monkeypatch.setattr(maintain_daily, "run_space_weather_backfill", record("omni"))
    monkeypatch.setattr(maintain_daily, "run_ephemeris_backfill", record("ephemeris"))

    summary = maintain_daily.run_daily_maintenance(
        run_ts=datetime(2024, 4, 15, 10, 37, tzinfo=UTC),
        symbols=("BTCUSDT",),
        archive_lookback_days=7,
        swpc_lookback_days=3,
        omni_lookback_days=75,
    )

    assert summary.run_ts == datetime(2024, 4, 15, 10, tzinfo=UTC)
    assert [task.name for task in summary.tasks] == [
        "binance_vision_metrics_recent",
        "goes_xray_recent",
        "noaa_swpc_recent_overlay",
        "nasa_omni_recent_authoritative",
        "ephemeris_recent_and_forward",
    ]
    assert calls[0][1]["start_utc"] == datetime(2024, 4, 8, 10, tzinfo=UTC)
    assert calls[2][1]["start_utc"] == datetime(2024, 4, 12, 10, tzinfo=UTC)
    assert calls[3][1]["start_utc"] == datetime(2024, 1, 31, 10, tzinfo=UTC)


def test_build_maintenance_scheduler_registers_hourly_and_daily_jobs():
    from astro_abm.etl.maintenance_daemon import build_maintenance_scheduler

    scheduler = build_maintenance_scheduler(
        symbols=("BTCUSDT",),
        daily_hour=3,
        daily_minute=25,
    )

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {"hourly_maintenance", "daily_maintenance"}
    assert str(jobs["hourly_maintenance"].trigger) == "cron[minute='5']"
    assert str(jobs["daily_maintenance"].trigger) == "cron[hour='3', minute='25']"


def test_build_maintenance_scheduler_can_disable_daily_job():
    from astro_abm.etl.maintenance_daemon import build_maintenance_scheduler

    scheduler = build_maintenance_scheduler(
        symbols=("BTCUSDT",),
        enable_daily=False,
    )

    assert [job.id for job in scheduler.get_jobs()] == ["hourly_maintenance"]
