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

ASKGROK_DEFAULT_BASE_URL = "http://localhost:3000"


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


def parse_askgrok_sentiment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sentiment = payload.get("sentiment", payload)
    if not isinstance(sentiment, dict):
        raise ValueError("ASKGROK response must contain a sentiment object.")
    return sentiment


def build_askgrok_feature_rows(*, sentiment: dict[str, Any], available_ts: datetime) -> list[dict[str, Any]]:
    ts = _parse_iso_utc(sentiment["timestamp_utc"])
    observed_ts = _parse_iso_utc(sentiment.get("window_end_utc", sentiment["timestamp_utc"]))
    assets = [str(asset).upper() for asset in sentiment.get("assets", []) if str(asset).strip()]
    entity_id = ",".join(assets) if assets else "CRYPTO"
    source = sentiment.get("source", "ASKGROK_WEB")

    metric_pairs = [
        ("askgrok_sentiment_score", sentiment.get("sentiment_score")),
        ("askgrok_confidence", sentiment.get("confidence")),
        ("askgrok_social_volume_proxy", sentiment.get("social_volume_proxy")),
        ("askgrok_bullish_intensity", sentiment.get("bullish_intensity")),
        ("askgrok_bearish_intensity", sentiment.get("bearish_intensity")),
        ("askgrok_fear_intensity", sentiment.get("fear_intensity")),
        ("askgrok_fomo_intensity", sentiment.get("fomo_intensity")),
        ("askgrok_uncertainty_intensity", sentiment.get("uncertainty_intensity")),
        ("askgrok_sample_size_estimate", sentiment.get("sample_size_estimate")),
    ]
    notes = _format_askgrok_notes(sentiment)
    rows: list[dict[str, Any]] = []
    for metric_name, metric_value in metric_pairs:
        number = _nullable_float(metric_value)
        if number is None:
            continue
        rows.append(
            {
                "ts": ts,
                "entity_type": "social_sentiment",
                "entity_id": entity_id,
                "source": source,
                "interval": "1h",
                "asset_class": "crypto",
                "market": sentiment.get("market", "crypto"),
                "region": "GLOBAL",
                "metric_name": metric_name,
                "metric_value": number,
                "observed_ts": observed_ts,
                "available_ts": available_ts,
                "quality_flag": "derived",
                "notes": notes,
            }
        )
    return rows


def _parse_iso_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _nullable_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    return number if number == number else None


def _format_askgrok_notes(sentiment: dict[str, Any]) -> str:
    parts = []
    for key in [
        "sentiment_label",
        "data_scope",
        "dominant_emotions",
        "dominant_topics",
        "notable_terms",
        "evidence_sources",
        "evidence_summary",
        "limitations",
    ]:
        value = sentiment.get(key)
        if value:
            parts.append(f"{key}={value}")
    return " | ".join(parts)


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


class AskGrokSentimentClient:
    def __init__(
        self,
        base_url: str = ASKGROK_DEFAULT_BASE_URL,
        timeout_ms: int = 180_000,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self.session = session or requests.Session()

    def fetch_sentiment(self, *, start_utc: datetime, end_utc: datetime, assets: list[str]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/sentiment/crypto",
            json={
                "startUtc": start_utc.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "endUtc": end_utc.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "assets": assets,
                "timeoutMs": self.timeout_ms,
            },
            timeout=(self.timeout_ms / 1000) + 10,
        )
        response.raise_for_status()
        return parse_askgrok_sentiment_payload(response.json())

    def fetch_feature_rows(self, *, start_utc: datetime, end_utc: datetime, assets: list[str]) -> list[dict[str, Any]]:
        sentiment = self.fetch_sentiment(start_utc=start_utc, end_utc=end_utc, assets=assets)
        return build_askgrok_feature_rows(sentiment=sentiment, available_ts=datetime.now(UTC))
