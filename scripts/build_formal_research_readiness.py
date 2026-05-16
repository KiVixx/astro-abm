#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.formal_readiness import build_formal_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Build formal research readiness report.")
    parser.add_argument("--market-features", default="astro_research/output/parquet/market_daily/market_daily_features.parquet")
    parser.add_argument("--market-bars", default="astro_research/output/parquet/market_daily/market_daily_bars.parquet")
    parser.add_argument("--macro-observations", default="astro_research/output/parquet/macro_daily/macro_daily_observations.parquet")
    parser.add_argument("--financial-stress", default="astro_research/output/parquet/financial_stress/financial_stress_daily.parquet")
    parser.add_argument("--provenance", default="astro_research/data/local/LOCAL_DATA_PROVENANCE.json")
    parser.add_argument("--market-config", default="astro_research/configs/market_assets_real.yaml")
    parser.add_argument("--macro-config", default="astro_research/configs/macro_series.yaml")
    parser.add_argument("--output-md", default="astro_research/output/reports/formal_research_readiness.md")
    parser.add_argument("--output-json", default="astro_research/output/reports/formal_research_readiness.json")
    parser.add_argument("--extreme-return-threshold", type=float, default=0.20)
    parser.add_argument("--long-flat-run-days", type=int, default=10)
    args = parser.parse_args()

    result = build_formal_readiness(
        root=ROOT,
        market_features_path=args.market_features,
        market_bars_path=args.market_bars,
        macro_observations_path=args.macro_observations,
        financial_stress_path=args.financial_stress,
        provenance_path=args.provenance,
        market_config_path=args.market_config,
        macro_config_path=args.macro_config,
        output_markdown_path=args.output_md,
        output_json_path=args.output_json,
        extreme_return_threshold=args.extreme_return_threshold,
        long_flat_run_days=args.long_flat_run_days,
    )
    print(f"status={result.status}")
    print(f"can_run_exploratory_formal_batch={result.can_run_exploratory_formal_batch}")
    print(f"warnings={json.dumps(result.warning_counts, sort_keys=True)}")
    print(f"markdown={ROOT / args.output_md}")
    print(f"json={ROOT / args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
