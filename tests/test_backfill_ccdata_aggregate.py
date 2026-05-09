from datetime import UTC, datetime, timedelta

from astro_abm.models import MarketBar


class FakeConnection:
    def cursor(self):
        return FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeCursor:
    last_sql = ""

    def execute(self, sql, params=None):
        FakeCursor.last_sql = sql

    def fetchall(self):
        if "SELECT ts, symbol" in FakeCursor.last_sql:
            return [
                (
                    datetime(2024, 4, 15, 0, tzinfo=UTC),
                    "BTCUSDT",
                    "binance",
                    "binance",
                    "spot",
                    "crypto",
                    100.0,
                    101.0,
                    99.0,
                    100.5,
                    10.0,
                    1000.0,
                ),
                (
                    datetime(2024, 4, 15, 4, tzinfo=UTC),
                    "BTCUSDT",
                    "binance",
                    "binance",
                    "spot",
                    "crypto",
                    104.0,
                    105.0,
                    103.0,
                    104.5,
                    20.0,
                    2000.0,
                ),
            ]
        if "SELECT ts" in FakeCursor.last_sql and "ORDER BY ts" in FakeCursor.last_sql:
            return [
                (datetime(2024, 4, 15, 0, tzinfo=UTC),),
                (datetime(2024, 4, 15, 1, tzinfo=UTC),),
                (datetime(2024, 4, 15, 4, tzinfo=UTC),),
            ]
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RecordingWriter:
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


def test_run_ccdata_aggregate_gap_backfill_scales_proxy_volume_and_logs_run():
    from astro_abm.etl.backfill_ccdata_aggregate import run_ccdata_aggregate_gap_backfill

    class FakeClient:
        def fetch_hourly_bars(self, *, symbol, start_ts, end_ts):
            bars = []
            current = start_ts
            while current < end_ts:
                bars.append(
                    MarketBar(
                        symbol=symbol,
                        ts=current,
                        open=100.0,
                        high=110.0,
                        low=90.0,
                        close=105.0,
                        volume=100.0,
                        source="ccdata_aggregate",
                        venue="ccdata",
                        market_type="aggregate_proxy",
                        asset_class="crypto",
                        quote_volume=10000.0,
                        quality_flag="proxy",
                        is_proxy_data=True,
                        raw_volume=100.0,
                        raw_quote_volume=10000.0,
                        conversion_type="direct",
                    )
                )
                current += timedelta(hours=1)
            return bars

    writer = RecordingWriter()
    run_writer = RecordingRunWriter()

    result = run_ccdata_aggregate_gap_backfill(
        symbols=("BTCUSDT",),
        start_utc=datetime(2024, 4, 15, 0, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 5, tzinfo=UTC),
        client=FakeClient(),
        writer=writer,
        run_writer=run_writer,
        context_hours=1,
        request_pause_seconds=0,
        run_id="ccdata-test",
    )

    assert result.gaps_seen == 1
    assert result.written == 2
    assert [row.ts for row in writer.rows] == [
        datetime(2024, 4, 15, 2, tzinfo=UTC),
        datetime(2024, 4, 15, 3, tzinfo=UTC),
    ]
    assert writer.rows[0].volume == 20.0
    assert writer.rows[0].raw_volume == 100.0
    assert writer.rows[0].volume_scale_ratio == 0.2
    assert writer.rows[0].quality_flag == "proxy"
    assert run_writer.records[0].provider == "ccdata_aggregate"
