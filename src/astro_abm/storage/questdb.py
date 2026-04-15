from __future__ import annotations

from typing import Callable, Iterable

from astro_abm.models import MarketBar


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
