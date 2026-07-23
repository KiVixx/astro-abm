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
    run_mercury_tsla_study,
    write_mercury_tsla_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Study TSLA behavior after Mercury retrograde-to-direct stations."
    )
    parser.add_argument(
        "--config",
        default="astro_research/configs/mercury_station_tsla.yaml",
    )
    parser.add_argument(
        "--output",
        default="astro_research/output/reports/mercury_station_tsla_v1",
    )
    parser.add_argument(
        "--refresh-tsla",
        action="store_true",
        help="Refresh the ignored local TSLA CSV from Yahoo before running.",
    )
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
            f"Missing ignored TSLA data: {tsla_path}. Re-run with --refresh-tsla."
        )
    if not spx_path.exists():
        raise FileNotFoundError(
            f"Missing local SPX benchmark: {spx_path}. Run the local-data fetch workflow."
        )

    tsla = load_price_csv(tsla_path, asset="TSLA")
    spx = load_price_csv(spx_path, asset="SPX")
    events = generate_mercury_station_out_events(
        start_ts=datetime.fromisoformat(str(station["scan_start"])).replace(tzinfo=UTC),
        end_ts=datetime.fromisoformat(str(station["scan_end"])).replace(tzinfo=UTC),
        step_hours=int(station["step_hours"]),
        tolerance_seconds=int(station["tolerance_seconds"]),
    )
    result = run_mercury_tsla_study(
        config=config,
        config_text=config_text,
        tsla=tsla,
        spx=spx,
        station_events=events,
    )
    paths = write_mercury_tsla_report(result, ROOT / args.output)
    print(
        f"events={len(result.station_events)} "
        f"completed_post14={result.data_quality['completed_station_out_events']} "
        f"result_rows={len(result.results)} "
        f"summary={paths['summary']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
