from __future__ import annotations

from typing import Callable

import pandas as pd

from astro_abm.storage.questdb import QuestDBMarketBarWriter
from astro_daily.ingest_questdb import _null_to_none


EVENT_STUDY_RESULT_COLUMNS = [
    "ts",
    "run_id",
    "event_type",
    "asset",
    "window_name",
    "metric",
    "effect_value",
    "baseline_value",
    "effect_minus_baseline",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "p_value",
    "q_value_fdr",
    "n_events",
    "n_observations",
    "data_version",
    "calc_version",
    "source_note",
]


def ingest_event_study_results(results: pd.DataFrame, *, connection_factory: Callable | None = None, batch_size: int = 1000) -> int:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    selected = results.reindex(columns=EVENT_STUDY_RESULT_COLUMNS)
    rows = [tuple(_null_to_none(value) for value in row) for row in selected.itertuples(index=False, name=None)]
    if not rows:
        return 0
    placeholders = ", ".join(["%s"] * len(EVENT_STUDY_RESULT_COLUMNS))
    sql = f"INSERT INTO event_study_results ({', '.join(EVENT_STUDY_RESULT_COLUMNS)}) VALUES ({placeholders})"
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            for index in range(0, len(rows), batch_size):
                cursor.executemany(sql, rows[index : index + batch_size])
        connection.commit()
    return len(rows)
