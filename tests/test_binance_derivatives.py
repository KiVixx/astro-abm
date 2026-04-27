from datetime import UTC, datetime


def test_build_funding_feature_rows_expands_eight_hour_rates_to_hourly_facts():
    from astro_abm.market_data.binance_derivatives import build_funding_feature_rows

    rows = build_funding_feature_rows(
        [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00010000",
                "fundingTime": 1713171600000,
                "markPrice": "65000.0",
            }
        ],
        end_ts=datetime(2024, 4, 15, 12, tzinfo=UTC),
        expand_hours=2,
    )

    funding_rows = [row for row in rows if row["metric_name"] == "funding_rate"]
    annualized_rows = [row for row in rows if row["metric_name"] == "funding_rate_annualized"]

    assert [row["ts"] for row in funding_rows] == [
        datetime(2024, 4, 15, 9, tzinfo=UTC),
        datetime(2024, 4, 15, 10, tzinfo=UTC),
    ]
    assert funding_rows[0]["metric_value"] == 0.0001
    assert annualized_rows[0]["metric_value"] == 0.0001 * 3 * 365
    assert funding_rows[0]["source"] == "binance_futures"
    assert funding_rows[0]["entity_type"] == "derivatives"


def test_build_open_interest_feature_rows_shapes_futures_metrics():
    from astro_abm.market_data.binance_derivatives import build_open_interest_feature_rows

    rows = build_open_interest_feature_rows(
        [
            {
                "symbol": "BTCUSDT",
                "sumOpenInterest": "20403.637",
                "sumOpenInterestValue": "150570784.078",
                "timestamp": "1713171600000",
            }
        ]
    )

    by_metric = {row["metric_name"]: row for row in rows}

    assert by_metric["open_interest"]["metric_value"] == 20403.637
    assert by_metric["open_interest_value"]["metric_value"] == 150570784.078
    assert by_metric["open_interest"]["ts"] == datetime(2024, 4, 15, 9, tzinfo=UTC)


def test_build_current_open_interest_feature_rows_shapes_forward_snapshot():
    from astro_abm.market_data.binance_derivatives import build_current_open_interest_feature_rows

    rows = build_current_open_interest_feature_rows(
        [
            {
                "symbol": "BTCUSDT",
                "openInterest": "20403.637",
                "time": 1713171900000,
            }
        ],
        bucket_ts=datetime(2024, 4, 15, 9, tzinfo=UTC),
    )

    assert rows[0]["source"] == "binance_futures_current"
    assert rows[0]["quality_flag"] == "official"
    assert rows[0]["metric_name"] == "open_interest"
    assert rows[0]["metric_value"] == 20403.637
    assert rows[0]["ts"] == datetime(2024, 4, 15, 9, tzinfo=UTC)


def test_binance_futures_client_uses_official_funding_endpoint():
    from astro_abm.market_data.binance_derivatives import BinanceFuturesDataClient

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    BinanceFuturesDataClient(base_url="https://example.test", session=FakeSession()).fetch_funding_rates(
        symbol="BTCUSDT",
        start_ts=datetime(2024, 4, 15, 0, tzinfo=UTC),
        end_ts=datetime(2024, 4, 16, 0, tzinfo=UTC),
    )

    assert calls[0]["url"] == "https://example.test/fapi/v1/fundingRate"
    assert calls[0]["params"]["symbol"] == "BTCUSDT"


def test_binance_futures_client_uses_current_open_interest_endpoint():
    from astro_abm.market_data.binance_derivatives import BinanceFuturesDataClient

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"symbol": "BTCUSDT", "openInterest": "1.0", "time": 1713171900000}

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    payload = BinanceFuturesDataClient(base_url="https://example.test", session=FakeSession()).fetch_current_open_interest(
        symbol="BTCUSDT"
    )

    assert payload["openInterest"] == "1.0"
    assert calls[0]["url"] == "https://example.test/fapi/v1/openInterest"
    assert calls[0]["params"]["symbol"] == "BTCUSDT"
