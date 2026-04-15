from datetime import UTC, datetime


def test_parse_lunarcrush_asset_timeseries_payload_normalizes_hourly_points():
    from astro_abm.features.social_sentiment import parse_lunarcrush_assets_payload

    payload = {
        "data": [
            {
                "id": 1,
                "symbol": "BTC",
                "timeSeries": [
                    {
                        "time": 1713171600,
                        "social_volume": 28124,
                        "social_contributors": 5342,
                        "social_score": 126598,
                        "average_sentiment": 3.9,
                        "sentiment": 0.73,
                        "social_dominance": 14.2,
                    }
                ],
            }
        ]
    }

    rows = parse_lunarcrush_assets_payload(payload)

    assert rows == [
        {
            "asset_id": 1,
            "symbol": "BTC",
            "ts": datetime(2024, 4, 15, 9, 0, tzinfo=UTC),
            "social_volume": 28124.0,
            "social_contributors": 5342.0,
            "social_score": 126598.0,
            "average_sentiment": 3.9,
            "sentiment_score": 0.73,
            "social_dominance": 14.2,
        }
    ]


def test_parse_lunarcrush_payload_tolerates_missing_optional_metrics():
    from astro_abm.features.social_sentiment import parse_lunarcrush_assets_payload

    payload = {
        "data": [
            {
                "id": 7,
                "symbol": "ETH",
                "timeSeries": [
                    {
                        "time": 1713175200,
                        "social_volume": 19000,
                        "sentiment": 0.61,
                    }
                ],
            }
        ]
    }

    rows = parse_lunarcrush_assets_payload(payload)

    assert rows[0]["symbol"] == "ETH"
    assert rows[0]["ts"] == datetime(2024, 4, 15, 10, 0, tzinfo=UTC)
    assert rows[0]["social_volume"] == 19000.0
    assert rows[0]["average_sentiment"] is None
    assert rows[0]["sentiment_score"] == 0.61


def test_build_social_sentiment_feature_rows_shapes_hourly_fact_rows():
    from astro_abm.features.social_sentiment import build_social_sentiment_feature_rows

    ts = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
    rows = build_social_sentiment_feature_rows(
        symbol="BTC",
        ts=ts,
        social_volume=28124.0,
        sentiment_score=0.73,
        social_contributors=5342.0,
        average_sentiment=3.9,
        social_dominance=14.2,
        observed_ts=ts,
        available_ts=datetime(2026, 4, 15, 12, 6, tzinfo=UTC),
    )

    metric_names = [row["metric_name"] for row in rows]
    assert metric_names == [
        "social_volume",
        "sentiment_score",
        "social_contributors",
        "average_sentiment",
        "social_dominance",
    ]
    assert all(row["entity_type"] == "social_sentiment" for row in rows)
    assert all(row["entity_id"] == "BTC" for row in rows)
    assert all(row["source"] == "lunarcrush" for row in rows)
    assert all(row["asset_class"] == "crypto" for row in rows)
