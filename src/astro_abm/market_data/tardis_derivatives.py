from __future__ import annotations

import csv
import gzip
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests


TARDIS_DATASETS_BASE_URL = "https://datasets.tardis.dev/v1"


@dataclass(frozen=True)
class TardisOpenInterestRecord:
    ts: datetime
    symbol: str
    open_interest: float
    mark_price: float | None

    @property
    def open_interest_value(self) -> float | None:
        if self.mark_price is None:
            return None
        return self.open_interest * self.mark_price


class TardisDerivativesClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = TARDIS_DATASETS_BASE_URL,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def fetch_daily_derivative_ticker_csv(self, *, exchange: str, symbol: str, day: date) -> bytes:
        url = (
            f"{self.base_url}/{exchange}/derivative_ticker/"
            f"{day.year:04d}/{day.month:02d}/{day.day:02d}/{symbol.upper()}.csv.gz"
        )
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = self.session.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        return response.content

    def download_daily_derivative_ticker_csv(self, *, exchange: str, symbol: str, day: date, cache_dir: Path) -> Path:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / exchange / "derivative_ticker" / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}" / f"{symbol.upper()}.csv.gz"
        if path.exists() and path.stat().st_size > 0:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.fetch_daily_derivative_ticker_csv(exchange=exchange, symbol=symbol, day=day)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(payload)
        tmp_path.replace(path)
        return path


def parse_tardis_derivative_ticker_open_interest(payload: bytes, *, symbol: str) -> list[TardisOpenInterestRecord]:
    with gzip.GzipFile(fileobj=BytesIO(payload)) as gz_file:
        return parse_tardis_derivative_ticker_open_interest_csv(
            TextIOWrapper(gz_file, encoding="utf-8"),
            symbol=symbol,
        )


def parse_tardis_derivative_ticker_open_interest_file(path: Path, *, symbol: str) -> list[TardisOpenInterestRecord]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return parse_tardis_derivative_ticker_open_interest_csv(handle, symbol=symbol)


def parse_tardis_derivative_ticker_open_interest_csv(handle: Iterable[str], *, symbol: str) -> list[TardisOpenInterestRecord]:
    rows = []
    reader = csv.DictReader(handle)
    for item in reader:
        open_interest = _nullable_float(item.get("open_interest"))
        if open_interest is None:
            continue
        rows.append(
            TardisOpenInterestRecord(
                ts=datetime.fromtimestamp(int(item["timestamp"]) / 1_000_000, tz=UTC),
                symbol=symbol.upper(),
                open_interest=open_interest,
                mark_price=_nullable_float(item.get("mark_price")),
            )
        )
    return rows


def aggregate_open_interest_hourly(records: Sequence[TardisOpenInterestRecord]) -> list[TardisOpenInterestRecord]:
    by_hour: OrderedDict[datetime, TardisOpenInterestRecord] = OrderedDict()
    for record in sorted(records, key=lambda item: item.ts):
        bucket = record.ts.replace(minute=0, second=0, microsecond=0)
        by_hour[bucket] = TardisOpenInterestRecord(
            ts=bucket,
            symbol=record.symbol,
            open_interest=record.open_interest,
            mark_price=record.mark_price,
        )
    return list(by_hour.values())


def build_tardis_open_interest_feature_rows(
    records: Sequence[TardisOpenInterestRecord],
    *,
    source: str = "tardis_binance_futures",
) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        rows.extend(
            _metric_rows(
                ts=record.ts,
                symbol=record.symbol,
                metrics=[
                    ("open_interest", record.open_interest),
                    ("open_interest_value", record.open_interest_value),
                ],
                source=source,
                notes="Tardis derivative_ticker hourly last open_interest.",
            )
        )
    return rows


def _metric_rows(*, ts: datetime, symbol: str, metrics: Sequence[tuple[str, float | None]], source: str, notes: str):
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
                "quality_flag": "vendor",
                "notes": notes,
            }
        )
    return rows


def iter_days(start_utc: datetime, end_utc: datetime):
    current = start_utc.astimezone(UTC).date()
    end_date = (end_utc.astimezone(UTC) - timedelta(microseconds=1)).date()
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _nullable_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
