from datetime import UTC, datetime


def test_binance_spot_historical_client_normalizes_klines_to_market_bars():
    from astro_abm.market_data.binance_historical import BinanceSpotHistoricalClient

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                [
                    1713171600000,
                    "100.0",
                    "110.0",
                    "95.0",
                    "105.0",
                    "12.0",
                    1713175199999,
                    "1260.0",
                    123,
                    "6.0",
                    "630.0",
                    "0",
                ]
            ]

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    bars = BinanceSpotHistoricalClient(base_url="https://example.test", session=FakeSession()).fetch_hourly_klines(
        symbol="BTCUSDT",
        start_ts=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_ts=datetime(2024, 4, 15, 10, tzinfo=UTC),
    )

    assert calls[0]["url"] == "https://example.test/api/v3/klines"
    assert calls[0]["params"]["interval"] == "1h"
    assert bars[0].symbol == "BTCUSDT"
    assert bars[0].ts == datetime(2024, 4, 15, 9, tzinfo=UTC)
    assert bars[0].close == 105.0
    assert bars[0].quote_volume == 1260.0


def test_binance_spot_historical_client_excludes_end_boundary_kline():
    from astro_abm.market_data.binance_historical import BinanceSpotHistoricalClient

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                [
                    1713171600000,
                    "100.0",
                    "110.0",
                    "95.0",
                    "105.0",
                    "12.0",
                    1713175199999,
                    "1260.0",
                    123,
                    "6.0",
                    "630.0",
                    "0",
                ],
                [
                    1713175200000,
                    "105.0",
                    "109.0",
                    "104.0",
                    "108.0",
                    "7.0",
                    1713178799999,
                    "756.0",
                    80,
                    "4.0",
                    "432.0",
                    "0",
                ],
            ]

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResponse()

    bars = BinanceSpotHistoricalClient(base_url="https://example.test", session=FakeSession()).fetch_hourly_klines(
        symbol="BTCUSDT",
        start_ts=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_ts=datetime(2024, 4, 15, 10, tzinfo=UTC),
    )

    assert [bar.ts for bar in bars] == [datetime(2024, 4, 15, 9, tzinfo=UTC)]
