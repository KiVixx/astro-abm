#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))

from research.local_data_fetch import fetch_yahoo_chart
from research.mercury_station_tsla import (
    generate_mercury_station_out_events,
    load_price_csv,
    load_study_config,
)
from research.mercury_station_tsla_reversal import (
    run_mercury_tsla_reversal_study,
    write_mercury_tsla_reversal_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Study TSLA trend reversal after Mercury station-out events."
    )
    parser.add_argument(
        "--config",
        default="astro_research/configs/mercury_station_tsla_reversal.yaml",
    )
    parser.add_argument(
        "--output",
        default="astro_research/output/reports/mercury_station_tsla_reversal_0_3_v3",
    )
    parser.add_argument("--refresh-tsla", action="store_true")
    args = parser.parse_args()

    config_path = ROOT / args.config
    config, config_text = load_study_config(config_path)
    study = config["study"]
    inputs = config["inputs"]
    station = config["station"]
    target_start = date.fromisoformat(str(study["target_start"]))
    target_end = date.fromisoformat(str(study["target_end"]))
    tsla_path = ROOT / str(inputs["tsla_path"])
    spx_path = ROOT / str(inputs["spx_path"])
    if args.refresh_tsla:
        frame = fetch_yahoo_chart("TSLA", start=target_start, end=target_end)
        tsla_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(tsla_path, index=False)
    if not tsla_path.exists():
        raise FileNotFoundError(
            f"Missing ignored TSLA data: {tsla_path}; use --refresh-tsla."
        )
    if not spx_path.exists():
        raise FileNotFoundError(f"Missing local SPX benchmark: {spx_path}.")

    tsla = load_price_csv(tsla_path, asset="TSLA")
    spx = load_price_csv(spx_path, asset="SPX")
    events = generate_mercury_station_out_events(
        start_ts=datetime.fromisoformat(str(station["scan_start"])).replace(
            tzinfo=UTC
        ),
        end_ts=datetime.fromisoformat(str(station["scan_end"])).replace(
            tzinfo=UTC
        ),
        step_hours=int(station["step_hours"]),
        tolerance_seconds=int(station["tolerance_seconds"]),
    )
    result = run_mercury_tsla_reversal_study(
        config=config,
        config_text=config_text,
        tsla=tsla,
        spx=spx,
        station_events=events,
    )
    paths = write_mercury_tsla_reversal_report(result, ROOT / args.output)
    primary = result.results[result.results["test_family"] == "primary_reversal"]
    print(
        f"events={len(result.station_events)} "
        f"result_rows={len(result.results)} "
        f"primary_rows={len(primary)} "
        f"primary_q_lt_0.10={int((primary['q_value_fdr'] < 0.10).sum())} "
        f"summary={paths['summary']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
