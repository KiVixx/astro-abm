from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

LUNARCRUSH_BASE_URL = "https://lunarcrush.com/api4/public"
DEFAULT_SYMBOL_TOPICS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "xrp",
    "DOGE": "dogecoin",
}


def _to_utc_hour(timestamp: int | float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC).replace(minute=0, second=0, microsecond=0)


def parse_lunarcrush_assets_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in payload.get("data", []):
        asset_id = asset.get("id")
        symbol = str(asset.get("symbol", "")).upper()
        for point in asset.get("timeSeries", []) or []:
            rows.append(
                {
                    "asset_id": asset_id,
                    "symbol": symbol,
                    "ts": _to_utc_hour(point["time"]),
                    "social_volume": float(point["social_volume"]) if point.get("social_volume") is not None else None,
                    "social_contributors": float(point["social_contributors"]) if point.get("social_contributors") is not None else None,
                    "social_score": float(point["social_score"]) if point.get("social_score") is not None else None,
                    "average_sentiment": float(point["average_sentiment"]) if point.get("average_sentiment") is not None else None,
                    "sentiment_score": float(point["sentiment"]) if point.get("sentiment") is not None else None,
                    "social_dominance": float(point["social_dominance"]) if point.get("social_dominance") is not None else None,
                }
            )
    return rows


def parse_lunarcrush_topic_timeseries_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    config = payload.get("config", {})
    symbol = str(config.get("symbol", "")).upper()
    asset_id = config.get("id")
    rows: list[dict[str, Any]] = []
    for point in payload.get("data", []) or []:
        posts_active = point.get("posts_active")
        posts_created = point.get("posts_created")
        social_volume = posts_active if posts_active is not None else posts_created
        rows.append(
            {
                "asset_id": asset_id,
                "symbol": symbol,
                "ts": _to_utc_hour(point["time"]),
                "social_volume": float(social_volume) if social_volume is not None else None,
                "social_contributors": float(point["contributors_active"])
                if point.get("contributors_active") is not None
                else None,
                "social_score": float(point["interactions"]) if point.get("interactions") is not None else None,
                "average_sentiment": None,
                "sentiment_score": float(point["sentiment"]) if point.get("sentiment") is not None else None,
                "social_dominance": float(point["social_dominance"])
                if point.get("social_dominance") is not None
                else None,
            }
        )
    return rows


def build_social_sentiment_feature_rows(
    *,
    symbol: str,
    ts: datetime,
    social_volume: float | None,
    sentiment_score: float | None,
    social_contributors: float | None = None,
    average_sentiment: float | None = None,
    social_dominance: float | None = None,
    observed_ts: datetime,
    available_ts: datetime,
) -> list[dict[str, Any]]:
    metrics = [
        ("social_volume", social_volume),
        ("sentiment_score", sentiment_score),
        ("social_contributors", social_contributors),
        ("average_sentiment", average_sentiment),
        ("social_dominance", social_dominance),
    ]
    rows: list[dict[str, Any]] = []
    for metric_name, metric_value in metrics:
        if metric_value is None:
            continue
        rows.append(
            {
                "ts": ts,
                "entity_type": "social_sentiment",
                "entity_id": symbol,
                "source": "lunarcrush",
                "interval": "1h",
                "asset_class": "crypto",
                "market": None,
                "region": "GLOBAL",
                "metric_name": metric_name,
                "metric_value": float(metric_value),
                "observed_ts": observed_ts,
                "available_ts": available_ts,
                "quality_flag": "final",
            }
        )
    return rows


class LunarCrushClient:
    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def fetch_asset_timeseries(self, symbol: str, hours_back: int = 168) -> dict[str, Any]:
        topic = DEFAULT_SYMBOL_TOPICS.get(symbol.upper(), symbol.lower())
        url = f"{LUNARCRUSH_BASE_URL}/topic/{topic}/time-series/v2"
        response = self.session.get(
            url,
            params={"bucket": "hour"},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def fetch_normalized_rows(self, symbol: str, hours_back: int = 168) -> list[dict[str, Any]]:
        payload = self.fetch_asset_timeseries(symbol=symbol, hours_back=hours_back)
        rows = parse_lunarcrush_topic_timeseries_payload(payload)
        if hours_back <= 0:
            return rows
        return rows[-hours_back:]
