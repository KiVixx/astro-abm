from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from astro_abm.etl.pipeline import FACT_ROW_COLUMNS
from astro_abm.models import MarketBar


@dataclass(frozen=True)
class ETLRunRecord:
    started_at: datetime
    run_id: str
    job_type: str
    provider: str
    window_start: datetime
    window_end: datetime
    status: str
    rows_written: int
    skipped_existing: int
    errors: int
    finished_at: datetime
    notes: str = ""


class QuestDBMarketBarWriter:
    def __init__(self, connection_factory: Callable | None = None):
        self.connection_factory = connection_factory or self._build_default_connection

    @staticmethod
    def _build_default_connection():
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for live QuestDB writes") from exc

        from astro_abm.config import load_questdb_settings

        settings = load_questdb_settings()
        return psycopg.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            dbname=settings.database,
        )

    def write(self, bars: Iterable[MarketBar]) -> None:
        rows = [
            (
                bar.ts,
                bar.symbol,
                bar.source,
                bar.venue,
                bar.market_type,
                bar.asset_class,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.quote_volume,
                bar.trade_count,
                bar.complete,
                bar.observed_ts,
                bar.available_ts,
            )
            for bar in bars
        ]
        if not rows:
            return

        sql = """
        INSERT INTO market_ohlcv_1h (
            ts,
            symbol,
            source,
            venue,
            market_type,
            asset_class,
            open,
            high,
            low,
            close,
            volume,
            quote_volume,
            trade_count,
            complete,
            observed_ts,
            available_ts
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """.strip()

        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
            connection.commit()


class QuestDBHourlyFactWriter:
    def __init__(self, connection_factory: Callable | None = None, batch_size: int = 100):
        self.connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
        self.batch_size = batch_size

    def write(self, facts: Iterable[dict | tuple]) -> None:
        rows = [self._shape_row(fact) for fact in facts]
        if not rows:
            return

        placeholders = ", ".join(["%s"] * len(FACT_ROW_COLUMNS))
        columns = ", ".join(FACT_ROW_COLUMNS)
        sql = f"INSERT INTO abm_hourly_facts ({columns}) VALUES ({placeholders})"

        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                for index in range(0, len(rows), self.batch_size):
                    cursor.executemany(sql, rows[index : index + self.batch_size])
            connection.commit()

    @staticmethod
    def _shape_row(fact: dict | tuple) -> tuple:
        if isinstance(fact, dict):
            return tuple(fact.get(column) for column in FACT_ROW_COLUMNS)
        return tuple(fact)


class QuestDBETLRunWriter:
    def __init__(self, connection_factory: Callable | None = None):
        self.connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection

    def write(self, record: ETLRunRecord) -> None:
        sql = """
        INSERT INTO etl_runs (
            started_at,
            run_id,
            job_type,
            provider,
            window_start,
            window_end,
            status,
            rows_written,
            skipped_existing,
            errors,
            finished_at,
            notes
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """.strip()
        row = (
            record.started_at,
            record.run_id,
            record.job_type,
            record.provider,
            record.window_start,
            record.window_end,
            record.status,
            record.rows_written,
            record.skipped_existing,
            record.errors,
            record.finished_at,
            record.notes,
        )

        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, row)
            connection.commit()


def askgrok_fact_exists(connection_factory: Callable, ts: datetime, entity_id: str) -> bool:
    sql = """
    SELECT count()
    FROM abm_hourly_facts
    WHERE ts = %s
      AND entity_id = %s
      AND source = 'ASKGROK_WEB'
      AND metric_name = 'askgrok_sentiment_score'
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (ts, entity_id))
            return cursor.fetchone()[0] > 0


def load_existing_market_timestamps(
    connection_factory: Callable,
    *,
    symbol: str,
    source: str,
    start_ts: datetime,
    end_ts: datetime,
) -> set[datetime]:
    sql = """
    SELECT ts
    FROM market_ohlcv_1h
    WHERE symbol = %s
      AND source = %s
      AND ts >= %s
      AND ts < %s
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (symbol, source, start_ts, end_ts))
            return {row[0].replace(tzinfo=start_ts.tzinfo) if row[0].tzinfo is None else row[0] for row in cursor.fetchall()}


def load_existing_fact_timestamps(
    connection_factory: Callable,
    *,
    entity_id: str,
    source: str,
    metric_name: str,
    start_ts: datetime,
    end_ts: datetime,
) -> set[datetime]:
    sql = """
    SELECT ts
    FROM abm_hourly_facts
    WHERE entity_id = %s
      AND source = %s
      AND metric_name = %s
      AND ts >= %s
      AND ts < %s
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (entity_id, source, metric_name, start_ts, end_ts))
            return {row[0].replace(tzinfo=start_ts.tzinfo) if row[0].tzinfo is None else row[0] for row in cursor.fetchall()}
