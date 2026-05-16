from __future__ import annotations

import math

import pandas as pd


BAR_COLUMNS = [
    "ts",
    "asset",
    "source",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "currency",
    "market_timezone",
    "data_version",
    "source_note",
]


def normalize_market_bars(
    frame: pd.DataFrame,
    *,
    asset: str,
    source: str,
    currency: str,
    market_timezone: str,
    data_version: str,
    source_note: str,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=BAR_COLUMNS)
    working = frame.copy()
    working.columns = [str(column).strip().lower().replace(" ", "_") for column in working.columns]
    if "date" in working.columns and "ts" not in working.columns:
        working = working.rename(columns={"date": "ts"})
    if "timestamp" in working.columns and "ts" not in working.columns:
        working = working.rename(columns={"timestamp": "ts"})
    if "adjclose" in working.columns and "adj_close" not in working.columns:
        working = working.rename(columns={"adjclose": "adj_close"})
    if "ts" not in working.columns:
        raise ValueError("Market CSV must contain one of: ts, date, timestamp.")

    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    for column in ("open", "high", "low", "close"):
        if column not in working.columns:
            working[column] = working.get("adj_close")
    if "adj_close" not in working.columns:
        working["adj_close"] = working["close"]
    if "volume" not in working.columns:
        working["volume"] = math.nan
    for column in ("open", "high", "low", "close", "adj_close", "volume"):
        working[column] = pd.to_numeric(working[column], errors="coerce")
    working["asset"] = asset
    working["source"] = source
    working["currency"] = currency
    working["market_timezone"] = market_timezone
    working["data_version"] = data_version
    working["source_note"] = source_note
    working = working.sort_values("ts").drop_duplicates(["ts", "asset", "source"], keep="last")
    return working[BAR_COLUMNS].reset_index(drop=True)
