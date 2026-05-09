from datetime import UTC, datetime

from astro_abm.models import MarketBar


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


class RecordingWriter:
    def __init__(self):
        self.rows = []
        self.connection_factory = lambda: FakeConnection()

    def write(self, rows):
        self.rows.extend(rows)


def test_run_binance_spot_backfill_drops_end_boundary_bar_before_write():
    from astro_abm.etl.backfill_binance_spot import run_binance_spot_backfill

    class FakeClient:
        def fetch_hourly_klines(self, *, symbol, start_ts, end_ts, max_requests):
            return [
                MarketBar(
                    symbol=symbol,
                    ts=datetime(2024, 4, 15, 9, tzinfo=UTC),
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=10.0,
                    source="binance",
                    venue="binance",
                    market_type="spot",
                    asset_class="crypto",
                ),
                MarketBar(
                    symbol=symbol,
                    ts=datetime(2024, 4, 15, 10, tzinfo=UTC),
                    open=100.5,
                    high=102.0,
                    low=100.0,
                    close=101.0,
                    volume=11.0,
                    source="binance",
                    venue="binance",
                    market_type="spot",
                    asset_class="crypto",
                ),
            ]

    writer = RecordingWriter()
    result = run_binance_spot_backfill(
        symbols=("BTCUSDT",),
        start_utc=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 10, tzinfo=UTC),
        client=FakeClient(),
        writer=writer,
    )

    assert result.fetched == 2
    assert result.written == 1
    assert [bar.ts for bar in writer.rows] == [datetime(2024, 4, 15, 9, tzinfo=UTC)]
