from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Sequence

import requests


COINALYZE_BASE_URL = "https://api.coinalyze.net/v1"


@dataclass(frozen=True)
class CoinalyzeOpenInterestPoint:
    ts: datetime
    entity_id: str
    coinalyze_symbol: str
    open_interest_open: float | None
    open_interest_high: float | None
    open_interest_low: float | None
    open_interest_close: float
    is_usd_value: bool = False


class CoinalyzeDerivativesClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = COINALYZE_BASE_URL,
        session: requests.Session | None = None,
    ):
        if not api_key:
            raise ValueError("COINALYZE_API_KEY is required for Coinalyze requests.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_open_interest_history(
        self,
        *,
        symbols: Sequence[str],
        interval: str,
        start_ts: datetime,
        end_ts: datetime,
        convert_to_usd: bool = False,
    ) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/open-interest-history",
            params={
                "symbols": ",".join(symbol.upper() for symbol in symbols),
                "interval": interval,
                "from": int(start_ts.astimezone(UTC).timestamp()),
                "to": int(end_ts.astimezone(UTC).timestamp()),
                "convert_to_usd": str(convert_to_usd).lower(),
            },
            headers={"api_key": self.api_key},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()


def parse_coinalyze_open_interest_history(
    payload: Iterable[dict[str, Any]],
    *,
    convert_to_usd: bool = False,
) -> list[CoinalyzeOpenInterestPoint]:
    points = []
    for item in payload:
        symbol = str(item["symbol"]).upper()
        entity_id = normalize_coinalyze_entity_id(symbol)
        for point in item.get("history", []):
            close_value = _nullable_float(point.get("c"))
            if close_value is None:
                continue
            points.append(
                CoinalyzeOpenInterestPoint(
                    ts=datetime.fromtimestamp(int(point["t"]), tz=UTC),
                    entity_id=entity_id,
                    coinalyze_symbol=symbol,
                    open_interest_open=_nullable_float(point.get("o")),
                    open_interest_high=_nullable_float(point.get("h")),
                    open_interest_low=_nullable_float(point.get("l")),
                    open_interest_close=close_value,
                    is_usd_value=convert_to_usd,
                )
            )
    return points


def build_coinalyze_open_interest_feature_rows(
    points: Sequence[CoinalyzeOpenInterestPoint],
    *,
    source: str = "coinalyze",
) -> list[dict[str, Any]]:
    rows = []
    for point in points:
        rows.append(
            {
                "ts": point.ts,
                "entity_type": "derivatives",
                "entity_id": point.entity_id,
                "source": source,
                "interval": "1h" if point.ts.minute == 0 else None,
                "asset_class": "crypto",
                "market": "perp",
                "region": "GLOBAL",
                "metric_name": "open_interest_value" if point.is_usd_value else "open_interest",
                "metric_value": point.open_interest_close,
                "metric_value_2": point.open_interest_open,
                "metric_value_3": point.open_interest_high,
                "metric_value_4": point.open_interest_low,
                "observed_ts": point.ts,
                "available_ts": point.ts,
                "quality_flag": "vendor",
                "notes": f"coinalyze_symbol={point.coinalyze_symbol}; ohlc_fields=close,open,high,low",
            }
        )
    return rows


def normalize_coinalyze_entity_id(symbol: str) -> str:
    base = symbol.upper().split(".")[0]
    if base.endswith("_PERP"):
        return base.removesuffix("_PERP")
    return base


def _nullable_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
