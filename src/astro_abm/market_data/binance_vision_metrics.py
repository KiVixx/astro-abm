from __future__ import annotations

import csv
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests


BINANCE_VISION_BASE_URL = "https://data.binance.vision/data/futures/um/daily/metrics"


@dataclass(frozen=True)
class BinanceVisionMetricRecord:
    ts: datetime
    symbol: str
    open_interest: float | None
    open_interest_value: float | None
    count_toptrader_long_short_ratio: float | None
    sum_toptrader_long_short_ratio: float | None
    count_long_short_ratio: float | None
    sum_taker_long_short_vol_ratio: float | None


class BinanceVisionMetricsClient:
    def __init__(self, base_url: str = BINANCE_VISION_BASE_URL, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_daily_metrics_zip(self, *, symbol: str, day: date) -> bytes:
        symbol = symbol.upper()
        filename = f"{symbol}-metrics-{day.isoformat()}.zip"
        response = self.session.get(f"{self.base_url}/{symbol}/{filename}", timeout=60)
        response.raise_for_status()
        return response.content

    def download_daily_metrics_zip(self, *, symbol: str, day: date, cache_dir: Path) -> Path:
        symbol = symbol.upper()
        filename = f"{symbol}-metrics-{day.isoformat()}.zip"
        path = cache_dir / "binance-vision" / "futures" / "um" / "daily" / "metrics" / symbol / filename
        if path.exists() and path.stat().st_size > 0:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.fetch_daily_metrics_zip(symbol=symbol, day=day)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(payload)
        tmp_path.replace(path)
        return path


def parse_binance_vision_metrics_zip(payload: bytes) -> list[BinanceVisionMetricRecord]:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if not names:
            return []
        with archive.open(names[0]) as handle:
            return parse_binance_vision_metrics_csv(TextIOWrapper(handle, encoding="utf-8"))


def parse_binance_vision_metrics_file(path: Path) -> list[BinanceVisionMetricRecord]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if not names:
            return []
        with archive.open(names[0]) as handle:
            return parse_binance_vision_metrics_csv(TextIOWrapper(handle, encoding="utf-8"))


def parse_binance_vision_metrics_csv(handle: Iterable[str]) -> list[BinanceVisionMetricRecord]:
    by_timestamp: OrderedDict[tuple[str, datetime], BinanceVisionMetricRecord] = OrderedDict()
    reader = csv.DictReader(handle)
    for item in reader:
        symbol = str(item["symbol"]).upper()
        ts = datetime.strptime(item["create_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        by_timestamp[(symbol, ts)] = BinanceVisionMetricRecord(
            ts=ts,
            symbol=symbol,
            open_interest=_nullable_float(item.get("sum_open_interest")),
            open_interest_value=_nullable_float(item.get("sum_open_interest_value")),
            count_toptrader_long_short_ratio=_nullable_float(item.get("count_toptrader_long_short_ratio")),
            sum_toptrader_long_short_ratio=_nullable_float(item.get("sum_toptrader_long_short_ratio")),
            count_long_short_ratio=_nullable_float(item.get("count_long_short_ratio")),
            sum_taker_long_short_vol_ratio=_nullable_float(item.get("sum_taker_long_short_vol_ratio")),
        )
    return list(by_timestamp.values())


def aggregate_binance_vision_metrics_hourly(records: Sequence[BinanceVisionMetricRecord]) -> list[BinanceVisionMetricRecord]:
    by_hour: OrderedDict[tuple[str, datetime], BinanceVisionMetricRecord] = OrderedDict()
    for record in sorted(records, key=lambda item: item.ts):
        bucket = record.ts.replace(minute=0, second=0, microsecond=0)
        by_hour[(record.symbol, bucket)] = BinanceVisionMetricRecord(
            ts=bucket,
            symbol=record.symbol,
            open_interest=record.open_interest,
            open_interest_value=record.open_interest_value,
            count_toptrader_long_short_ratio=record.count_toptrader_long_short_ratio,
            sum_toptrader_long_short_ratio=record.sum_toptrader_long_short_ratio,
            count_long_short_ratio=record.count_long_short_ratio,
            sum_taker_long_short_vol_ratio=record.sum_taker_long_short_vol_ratio,
        )
    return list(by_hour.values())


def build_binance_vision_metric_feature_rows(
    records: Sequence[BinanceVisionMetricRecord],
    *,
    source: str = "binance_vision_metrics",
) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        rows.extend(
            _metric_rows(
                ts=record.ts,
                symbol=record.symbol,
                source=source,
                metrics=[
                    ("open_interest", record.open_interest),
                    ("open_interest_value", record.open_interest_value),
                    ("count_toptrader_long_short_ratio", record.count_toptrader_long_short_ratio),
                    ("sum_toptrader_long_short_ratio", record.sum_toptrader_long_short_ratio),
                    ("count_long_short_ratio", record.count_long_short_ratio),
                    ("sum_taker_long_short_vol_ratio", record.sum_taker_long_short_vol_ratio),
                ],
            )
        )
    return rows


def iter_days(start_utc: datetime, end_utc: datetime):
    current = start_utc.astimezone(UTC).date()
    end_date = (end_utc.astimezone(UTC) - timedelta(microseconds=1)).date()
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _metric_rows(*, ts: datetime, symbol: str, source: str, metrics: Sequence[tuple[str, float | None]]):
    rows = []
    for metric_name, metric_value in metrics:
        if metric_value is None:
            continue
        rows.append(
            {
                "ts": ts,
                "entity_type": "derivatives",
                "entity_id": symbol,
                "source": source,
                "interval": "1h",
                "asset_class": "crypto",
                "market": "perp",
                "region": "GLOBAL",
                "metric_name": metric_name,
                "metric_value": metric_value,
                "observed_ts": ts,
                "available_ts": ts,
                "quality_flag": "official",
                "notes": "Binance Vision UM daily metrics; hourly last 5m snapshot.",
            }
        )
    return rows


def _nullable_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
