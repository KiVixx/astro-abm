#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.validation import validate_research_layer


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MVP5 research outputs.")
    parser.add_argument("--output", default="astro_research/output/reports/research_layer_validation.md")
    parser.add_argument("--event-study-results", default="astro_research/output/reports/research_batch_v1/results.parquet")
    args = parser.parse_args()
    report, warnings = validate_research_layer(
        root=ROOT,
        output_path=ROOT / args.output,
        paths={
            "market_daily_features": "astro_research/output/parquet/market_daily/market_daily_features.parquet",
            "macro_daily_observations": "astro_research/output/parquet/macro_daily/macro_daily_observations.parquet",
            "financial_stress_daily": "astro_research/output/parquet/financial_stress/financial_stress_daily.parquet",
            "research_events": "astro_research/output/parquet/research_events/research_events.parquet",
            "research_hypotheses": "astro_research/output/parquet/research_hypotheses/research_hypotheses.parquet",
            "event_study_results_v2": args.event_study_results,
        },
    )
    print(f"report={report} warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
