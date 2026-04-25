from datetime import UTC, datetime


def test_binance_hourly_klines_are_normalized_with_hour_interval():
    from astro_abm.market_data.binance_client import BinanceMarketDataClient

    class FakeClient:
        KLINE_INTERVAL_1HOUR = "1h"

        def __init__(self):
            self.calls = []

        def get_klines(self, **kwargs):
            self.calls.append(kwargs)
            return [[
                1713171600000,
                "84500.10",
                "84620.50",
                "84480.00",
                "84550.25",
                "123.45",
                1713175199999,
                "10424567.89",
                9876,
                "62.10",
                "5250000.00",
                "0",
            ]]

    fake_client = FakeClient()
    provider = BinanceMarketDataClient(client=fake_client)

    bars = provider.fetch_recent_hourly_bars(symbol="BTCUSDT", limit=1)

    assert fake_client.calls == [{"symbol": "BTCUSDT", "interval": "1h", "limit": 1}]
    assert len(bars) == 1
    bar = bars[0]
    assert bar.symbol == "BTCUSDT"
    assert bar.source == "binance"
    assert bar.ts == datetime(2024, 4, 15, 9, 0, tzinfo=UTC)
    assert bar.open == 84500.10
    assert bar.high == 84620.50
    assert bar.low == 84480.00
    assert bar.close == 84550.25
    assert bar.volume == 123.45
    assert bar.quote_volume == 10424567.89
    assert bar.trade_count == 9876
    assert bar.complete is True


def test_polygon_hourly_response_is_normalized_to_market_bar():
    from astro_abm.market_data.tradfi import PolygonProvider

    provider = PolygonProvider(api_key="test-key")
    payload = {
        "ticker": "SPY",
        "results": [
            {
                "o": 511.9,
                "h": 512.5,
                "l": 511.7,
                "c": 512.1,
                "v": 1234567,
                "vw": 512.34,
                "t": 1713171600000,
                "n": 54321,
            }
        ],
    }

    bars = provider.parse_aggregate_response(payload)

    assert len(bars) == 1
    bar = bars[0]
    assert bar.symbol == "SPY"
    assert bar.source == "polygon"
    assert bar.market_type == "etf"
    assert bar.asset_class == "tradfi"
    assert bar.ts == datetime(2024, 4, 15, 9, 0, tzinfo=UTC)
    assert bar.vwap == 512.34
    assert bar.trade_count == 54321


def test_alpha_vantage_60min_response_is_converted_from_us_eastern_to_utc():
    from astro_abm.market_data.tradfi import AlphaVantageProvider

    provider = AlphaVantageProvider(api_key="test-key")
    payload = {
        "Meta Data": {
            "2. Symbol": "SPY",
            "6. Time Zone": "US/Eastern",
        },
        "Time Series (60min)": {
            "2024-04-15 11:00:00": {
                "1. open": "511.90",
                "2. high": "512.50",
                "3. low": "511.70",
                "4. close": "512.10",
                "5. volume": "1234567",
            }
        },
    }

    bars = provider.parse_intraday_response(payload)

    assert len(bars) == 1
    bar = bars[0]
    assert bar.symbol == "SPY"
    assert bar.source == "alpha_vantage"
    assert bar.ts == datetime(2024, 4, 15, 15, 0, tzinfo=UTC)
    assert bar.open == 511.9
    assert bar.close == 512.1
    assert bar.vwap is None
    assert bar.trade_count is None


def test_questdb_writer_executes_batch_insert_for_market_bars():
    from astro_abm.models import MarketBar
    from astro_abm.storage.questdb import QuestDBMarketBarWriter

    executed = {}

    class FakeCursor:
        def executemany(self, sql, rows):
            executed["sql"] = sql
            executed["rows"] = rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def __init__(self):
            self.committed = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_connection = FakeConnection()
    writer = QuestDBMarketBarWriter(connection_factory=lambda: fake_connection)
    bars = [
        MarketBar(
            symbol="BTCUSDT",
            ts=datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
            open=84500.1,
            high=84620.5,
            low=84480.0,
            close=84550.25,
            volume=123.45,
            source="binance",
            venue="binance",
            market_type="spot",
            asset_class="crypto",
            quote_volume=10424567.89,
            trade_count=9876,
            observed_ts=datetime(2024, 4, 15, 15, 59, 59, tzinfo=UTC),
            available_ts=datetime(2024, 4, 15, 16, 0, 5, tzinfo=UTC),
            complete=True,
        )
    ]

    writer.write(bars)

    assert "INSERT INTO market_ohlcv_1h" in executed["sql"]
    assert len(executed["rows"]) == 1
    row = executed["rows"][0]
    assert row[0] == datetime(2024, 4, 15, 15, 0, tzinfo=UTC)
    assert row[1] == "BTCUSDT"
    assert row[2] == "binance"
    assert row[6] == 84500.1
    assert row[13] is True
    assert fake_connection.committed is True


def test_questdb_fact_writer_executes_batch_insert_for_hourly_facts():
    from astro_abm.storage.questdb import QuestDBHourlyFactWriter

    executed = {}

    class FakeCursor:
        def executemany(self, sql, rows):
            executed["sql"] = sql
            executed["rows"] = rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def __init__(self):
            self.committed = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_connection = FakeConnection()
    writer = QuestDBHourlyFactWriter(connection_factory=lambda: fake_connection)

    writer.write(
        [
            {
                "ts": datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
                "entity_type": "ephemeris",
                "entity_id": "GLOBAL",
                "source": "pyswisseph",
                "interval": "1h",
                "asset_class": "macro",
                "region": "GLOBAL",
                "metric_name": "moon_phase_pct",
                "metric_value": 72.5,
                "observed_ts": datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
                "available_ts": datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
                "quality_flag": "derived",
            }
        ]
    )

    assert "INSERT INTO abm_hourly_facts" in executed["sql"]
    assert len(executed["rows"]) == 1
    row = executed["rows"][0]
    assert row[0] == datetime(2024, 4, 15, 15, 0, tzinfo=UTC)
    assert row[1] == "ephemeris"
    assert row[8] == "moon_phase_pct"
    assert row[9] == 72.5
    assert row[17] is None
    assert fake_connection.committed is True
