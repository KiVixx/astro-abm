from __future__ import annotations

from typing import Callable

import pandas as pd

from astro_daily.ingest_questdb import _null_to_none
from astro_abm.storage.questdb import QuestDBMarketBarWriter
from market_daily.features import FEATURE_COLUMNS
from market_daily.normalize import BAR_COLUMNS


TABLE_COLUMNS = {
    "market_daily_bars": BAR_COLUMNS,
    "market_daily_features": FEATURE_COLUMNS,
}


def ingest_market_frames(
    *,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    connection_factory: Callable | None = None,
    batch_size: int = 1000,
) -> dict[str, int]:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    frames = {
        "market_daily_bars": bars,
        "market_daily_features": features,
    }
    counts: dict[str, int] = {}
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            for table, frame in frames.items():
                columns = TABLE_COLUMNS[table]
                selected = frame.reindex(columns=columns)
                rows = [tuple(_null_to_none(value) for value in row) for row in selected.itertuples(index=False, name=None)]
                if not rows:
                    counts[table] = 0
                    continue
                placeholders = ", ".join(["%s"] * len(columns))
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                for index in range(0, len(rows), batch_size):
                    cursor.executemany(sql, rows[index : index + batch_size])
                counts[table] = len(rows)
        connection.commit()
    return counts
