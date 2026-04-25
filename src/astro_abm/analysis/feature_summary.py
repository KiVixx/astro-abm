from __future__ import annotations

import argparse
from typing import Sequence

from astro_abm.storage.questdb import QuestDBMarketBarWriter


def load_feature_summary(limit: int = 10, connection_factory=None) -> dict:
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count() FROM market_ohlcv_1h")
            market_count = cursor.fetchone()[0]
            cursor.execute("SELECT count() FROM abm_hourly_facts")
            fact_count = cursor.fetchone()[0]
            cursor.execute("SELECT source, count() FROM abm_hourly_facts GROUP BY source ORDER BY source")
            facts_by_source = cursor.fetchall()
            cursor.execute("SELECT count() FROM etl_runs")
            etl_run_count = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT ts, entity_id, metric_value
                FROM abm_hourly_facts
                WHERE source = 'ASKGROK_WEB'
                  AND metric_name = 'askgrok_sentiment_score'
                ORDER BY ts DESC
                LIMIT %s
                """.strip(),
                (limit,),
            )
            askgrok_sentiment = cursor.fetchall()
    return {
        "market_count": market_count,
        "fact_count": fact_count,
        "facts_by_source": facts_by_source,
        "etl_run_count": etl_run_count,
        "askgrok_sentiment": askgrok_sentiment,
    }


def format_feature_summary(summary: dict) -> str:
    lines = [
        f"market_ohlcv_1h rows: {summary['market_count']}",
        f"abm_hourly_facts rows: {summary['fact_count']}",
        f"etl_runs rows: {summary['etl_run_count']}",
        "facts by source:",
    ]
    lines.extend(f"  - {source}: {count}" for source, count in summary["facts_by_source"])
    lines.append("recent ASKGROK sentiment:")
    if summary["askgrok_sentiment"]:
        lines.extend(
            f"  - {ts} {entity_id}: {value}"
            for ts, entity_id, value in summary["askgrok_sentiment"]
        )
    else:
        lines.append("  - none")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a compact QuestDB feature-store summary.")
    parser.add_argument("--limit", type=int, default=10, help="Recent ASKGROK sentiment rows to show.")
    args = parser.parse_args(argv)
    print(format_feature_summary(load_feature_summary(limit=args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
