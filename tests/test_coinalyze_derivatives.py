from datetime import UTC, datetime


def test_parse_coinalyze_open_interest_history_shapes_points():
    from astro_abm.market_data.coinalyze_derivatives import parse_coinalyze_open_interest_history

    points = parse_coinalyze_open_interest_history(
        [
            {
                "symbol": "BTCUSDT_PERP.A",
                "history": [
                    {"t": 1713171600, "o": 100.0, "h": 120.0, "l": 90.0, "c": 110.0},
                    {"t": 1713175200, "o": None, "h": None, "l": None, "c": None},
                ],
            }
        ]
    )

    assert len(points) == 1
    assert points[0].ts == datetime(2024, 4, 15, 9, tzinfo=UTC)
    assert points[0].entity_id == "BTCUSDT"
    assert points[0].coinalyze_symbol == "BTCUSDT_PERP.A"
    assert points[0].open_interest_close == 110.0


def test_build_coinalyze_open_interest_feature_rows_stores_ohlc_fields():
    from astro_abm.market_data.coinalyze_derivatives import (
        build_coinalyze_open_interest_feature_rows,
        parse_coinalyze_open_interest_history,
    )

    points = parse_coinalyze_open_interest_history(
        [
            {
                "symbol": "BTCUSDT_PERP.A",
                "history": [{"t": 1713171600, "o": 100.0, "h": 120.0, "l": 90.0, "c": 110.0}],
            }
        ],
        convert_to_usd=True,
    )
    rows = build_coinalyze_open_interest_feature_rows(points)

    assert rows[0]["source"] == "coinalyze"
    assert rows[0]["quality_flag"] == "vendor"
    assert rows[0]["entity_id"] == "BTCUSDT"
    assert rows[0]["metric_name"] == "open_interest_value"
    assert rows[0]["metric_value"] == 110.0
    assert rows[0]["metric_value_2"] == 100.0
    assert rows[0]["metric_value_3"] == 120.0
    assert rows[0]["metric_value_4"] == 90.0


def test_coinalyze_client_sends_api_key_and_history_params():
    from astro_abm.market_data.coinalyze_derivatives import CoinalyzeDerivativesClient

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

    CoinalyzeDerivativesClient(api_key="key", base_url="https://example.test", session=FakeSession()).fetch_open_interest_history(
        symbols=("BTCUSDT_PERP.A",),
        interval="1hour",
        start_ts=datetime(2024, 4, 15, 0, tzinfo=UTC),
        end_ts=datetime(2024, 4, 16, 0, tzinfo=UTC),
        convert_to_usd=True,
    )

    assert calls[0]["url"] == "https://example.test/open-interest-history"
    assert calls[0]["headers"]["api_key"] == "key"
    assert calls[0]["params"]["symbols"] == "BTCUSDT_PERP.A"
    assert calls[0]["params"]["interval"] == "1hour"
    assert calls[0]["params"]["convert_to_usd"] == "true"
