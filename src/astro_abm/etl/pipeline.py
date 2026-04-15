from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

import pandas as pd


FACT_ROW_COLUMNS = [
    "ts",
    "entity_type",
    "entity_id",
    "source",
    "interval",
    "asset_class",
    "market",
    "region",
    "metric_name",
    "metric_value",
    "metric_value_2",
    "metric_value_3",
    "metric_value_4",
    "observed_ts",
    "available_ts",
    "quality_flag",
    "ingest_run_id",
    "notes",
]


def normalize_to_utc_hour(value) -> datetime:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(UTC)
    else:
        ts = ts.tz_convert(UTC)
    return ts.floor("h").to_pydatetime()


def align_tradfi_hourly(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    df = frame.copy()
    df["ts"] = df["ts"].apply(normalize_to_utc_hour)
    df = df.sort_values("ts")
    start = df["ts"].min()
    end = df["ts"].max()
    hourly_index = pd.date_range(start=start, end=end, freq="1h", tz=UTC)
    aligned = (
        df.set_index(pd.DatetimeIndex(df["ts"]))
        .drop(columns=["ts"])
        .reindex(hourly_index)
        .ffill()
        .reset_index()
        .rename(columns={"index": "ts"})
    )
    aligned["ts"] = pd.to_datetime(aligned["ts"], utc=True)
    aligned["symbol"] = aligned.get("symbol", symbol).fillna(symbol)
    return aligned


def merge_hourly_frames(frames: Iterable[pd.DataFrame], on: list[str]) -> pd.DataFrame:
    iterator = iter(frames)
    merged = next(iterator).copy()
    for frame in iterator:
        merged = merged.merge(frame, on=on, how="left")
    return merged


def dataframe_to_hourly_fact_rows(frame: pd.DataFrame) -> list[tuple]:
    rows: list[tuple] = []
    for record in frame.to_dict(orient="records"):
        rows.append(tuple(record.get(column) for column in FACT_ROW_COLUMNS))
    return rows
