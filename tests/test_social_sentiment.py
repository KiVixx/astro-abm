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


def test_parse_lunarcrush_v4_topic_timeseries_payload_normalizes_hourly_points():
    from astro_abm.features.social_sentiment import parse_lunarcrush_topic_timeseries_payload

    payload = {
        "config": {"id": "bitcoin", "symbol": "BTC"},
        "data": [
            {
                "time": 1713171600,
                "posts_active": 40278,
                "contributors_active": 20823,
                "interactions": 5345455,
                "sentiment": 72,
                "social_dominance": 33.9255,
            }
        ],
    }

    rows = parse_lunarcrush_topic_timeseries_payload(payload)

    assert rows == [
        {
            "asset_id": "bitcoin",
            "symbol": "BTC",
            "ts": datetime(2024, 4, 15, 9, 0, tzinfo=UTC),
            "social_volume": 40278.0,
            "social_contributors": 20823.0,
            "social_score": 5345455.0,
            "average_sentiment": None,
            "sentiment_score": 72.0,
            "social_dominance": 33.9255,
        }
    ]


def test_lunarcrush_client_uses_v4_topic_endpoint_and_bearer_token():
    from astro_abm.features.social_sentiment import LunarCrushClient

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "config": {"id": "bitcoin", "symbol": "BTC"},
                "data": [
                    {
                        "time": 1713171600,
                        "posts_active": 1,
                        "contributors_active": 2,
                        "interactions": 3,
                        "sentiment": 72,
                    },
                    {
                        "time": 1713175200,
                        "posts_active": 4,
                        "contributors_active": 5,
                        "interactions": 6,
                        "sentiment": 73,
                    },
                ],
            }

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    rows = LunarCrushClient(api_key="secret-token", session=FakeSession()).fetch_normalized_rows(
        symbol="BTC",
        hours_back=1,
    )

    assert calls == [
        {
            "url": "https://lunarcrush.com/api4/public/topic/bitcoin/time-series/v2",
            "params": {"bucket": "hour"},
            "headers": {"Authorization": "Bearer secret-token"},
            "timeout": 30,
        }
    ]
    assert len(rows) == 1
    assert rows[0]["ts"] == datetime(2024, 4, 15, 10, 0, tzinfo=UTC)
    assert rows[0]["sentiment_score"] == 73.0


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


def test_build_askgrok_feature_rows_shapes_hourly_fact_rows():
    from astro_abm.features.social_sentiment import build_askgrok_feature_rows

    sentiment = {
        "timestamp_utc": "2022-05-20T00:00:00.000Z",
        "window_end_utc": "2022-05-20T01:00:00.000Z",
        "source": "ASKGROK_WEB",
        "data_scope": "web_research",
        "market": "crypto",
        "assets": ["BTC", "ETH", "LUNA", "UST"],
        "sentiment_score": -0.75,
        "sentiment_label": "fear",
        "confidence": 0.65,
        "social_volume_proxy": None,
        "bullish_intensity": 0.1,
        "bearish_intensity": 0.8,
        "fear_intensity": 0.85,
        "fomo_intensity": 0.05,
        "uncertainty_intensity": 0.6,
        "dominant_emotions": ["fear", "panic"],
        "dominant_topics": ["Terra collapse aftermath"],
        "evidence_summary": "Broad fear after the UST depeg.",
        "sample_size_estimate": 50,
        "limitations": "Retrospective web research.",
    }

    rows = build_askgrok_feature_rows(
        sentiment=sentiment,
        available_ts=datetime(2026, 4, 25, 3, 5, tzinfo=UTC),
    )

    metric_names = [row["metric_name"] for row in rows]
    assert metric_names == [
        "askgrok_sentiment_score",
        "askgrok_confidence",
        "askgrok_bullish_intensity",
        "askgrok_bearish_intensity",
        "askgrok_fear_intensity",
        "askgrok_fomo_intensity",
        "askgrok_uncertainty_intensity",
        "askgrok_sample_size_estimate",
    ]
    assert rows[0]["ts"] == datetime(2022, 5, 20, 0, 0, tzinfo=UTC)
    assert rows[0]["observed_ts"] == datetime(2022, 5, 20, 1, 0, tzinfo=UTC)
    assert rows[0]["entity_id"] == "BTC,ETH,LUNA,UST"
    assert rows[0]["source"] == "ASKGROK_WEB"
    assert rows[0]["metric_value"] == -0.75
    assert "sentiment_label=fear" in rows[0]["notes"]


def test_askgrok_client_posts_window_and_assets_to_local_service():
    from astro_abm.features.social_sentiment import AskGrokSentimentClient

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "sentiment": {
                    "timestamp_utc": "2022-05-20T00:00:00.000Z",
                    "window_end_utc": "2022-05-20T01:00:00.000Z",
                    "source": "ASKGROK_WEB",
                    "assets": ["BTC"],
                    "sentiment_score": -0.5,
                    "confidence": 0.6,
                }
            }

    class FakeSession:
        def post(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    client = AskGrokSentimentClient(base_url="http://askgrok.test/", timeout_ms=180000, session=FakeSession())
    sentiment = client.fetch_sentiment(
        start_utc=datetime(2022, 5, 20, 0, 0, tzinfo=UTC),
        end_utc=datetime(2022, 5, 20, 1, 0, tzinfo=UTC),
        assets=["BTC"],
    )

    assert calls == [
        {
            "url": "http://askgrok.test/sentiment/crypto",
            "json": {
                "startUtc": "2022-05-20T00:00:00Z",
                "endUtc": "2022-05-20T01:00:00Z",
                "assets": ["BTC"],
                "timeoutMs": 180000,
            },
            "timeout": 190.0,
        }
    ]
    assert sentiment["sentiment_score"] == -0.5
