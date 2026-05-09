from __future__ import annotations

import argparse
from typing import Sequence

from astro_abm.analysis.data_completeness import INACTIVE_SOURCES
from astro_abm.storage.questdb import QuestDBMarketBarWriter


def load_feature_summary(limit: int = 10, connection_factory=None) -> dict:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    inactive_sources = ", ".join(f"'{source}'" for source in INACTIVE_SOURCES)
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count() FROM market_ohlcv_1h")
            market_count = cursor.fetchone()[0]
            cursor.execute("SELECT count() FROM abm_hourly_facts")
            fact_count = cursor.fetchone()[0]
            cursor.execute(
                f"""
                SELECT source, count()
                FROM abm_hourly_facts
                WHERE source NOT IN ({inactive_sources})
                  AND NOT (source = 'binance' AND entity_type = 'crypto_ohlcv')
                  AND NOT (source IN ('nasa_omni', 'noaa_goes_xrs', 'pyswisseph') AND quality_flag IN ('derived', 'final'))
                GROUP BY source
                ORDER BY source
                """.strip()
            )
            facts_by_source = cursor.fetchall()
            cursor.execute("SELECT count() FROM etl_runs")
            etl_run_count = cursor.fetchone()[0]
    return {
        "market_count": market_count,
        "fact_count": fact_count,
        "facts_by_source": facts_by_source,
        "etl_run_count": etl_run_count,
    }


def format_feature_summary(summary: dict) -> str:
    lines = [
        f"market_ohlcv_1h rows: {summary['market_count']}",
        f"abm_hourly_facts rows: {summary['fact_count']}",
        f"etl_runs rows: {summary['etl_run_count']}",
        "facts by source:",
    ]
    lines.extend(f"  - {source}: {count}" for source, count in summary["facts_by_source"])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a compact QuestDB feature-store summary.")
    parser.add_argument("--limit", type=int, default=10, help="Reserved for backward-compatible CLI calls.")
    args = parser.parse_args(argv)
    print(format_feature_summary(load_feature_summary(limit=args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
