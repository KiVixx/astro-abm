from datetime import UTC, datetime


def test_ccdata_aggregate_client_normalizes_histohour_rows():
    from astro_abm.market_data.ccdata import CCDataAggregateClient

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "Response": "Success",
                "Data": {
                    "Data": [
                        {
                            "time": 1713171600,
                            "open": 100.0,
                            "high": 110.0,
                            "low": 95.0,
                            "close": 105.0,
                            "volumefrom": 12.0,
                            "volumeto": 1260.0,
                            "conversionType": "direct",
                        }
                    ]
                },
            }

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    bars = CCDataAggregateClient(base_url="https://example.test", session=FakeSession()).fetch_hourly_bars(
        symbol="BTCUSDT",
        start_ts=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_ts=datetime(2024, 4, 15, 10, tzinfo=UTC),
        pause_seconds=0,
    )

    assert calls[0]["url"] == "https://example.test/data/v2/histohour"
    assert calls[0]["params"]["fsym"] == "BTC"
    assert calls[0]["params"]["tsym"] == "USDT"
    assert bars[0].source == "ccdata_aggregate"
    assert bars[0].market_type == "aggregate_proxy"
    assert bars[0].quality_flag == "proxy"
    assert bars[0].is_proxy_data is True
    assert bars[0].raw_volume == 12.0
    assert bars[0].conversion_type == "direct"


def test_split_market_symbol_supports_common_quotes():
    from astro_abm.market_data.ccdata import split_market_symbol

    assert split_market_symbol("BTCUSDT") == ("BTC", "USDT")
    assert split_market_symbol("ETHUSD") == ("ETH", "USD")
