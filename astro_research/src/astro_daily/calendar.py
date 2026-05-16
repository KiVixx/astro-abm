from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Iterator


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def utc_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def daily_datetimes(start: date, end: date) -> Iterator[datetime]:
    current = start
    while current <= end:
        yield utc_midnight(current)
        current += timedelta(days=1)


def day_count(start: date, end: date) -> int:
    return (end - start).days + 1
