#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.prepare import prepare_research


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare optional Astro ABM research data layers.")
    parser.add_argument("--mode", choices=("public", "local-full", "formal"), default="public")
    parser.add_argument("--start", default="1926-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--aspect-profile", default="macro_core")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--run-batch", action="store_true", help="In formal mode, run the exploratory formal batch after inputs are built.")
    parser.add_argument("--dry-run", action="store_true", help="Write a plan report without executing commands.")
    parser.add_argument("--strict-local-data", action="store_true", help="Fail local-full/formal mode if optional local CSV files are missing.")
    args = parser.parse_args()

    result = prepare_research(
        root=ROOT,
        mode=args.mode,
        start=args.start,
        end=args.end,
        aspect_profile=args.aspect_profile,
        workers=args.workers,
        ingest=args.ingest,
        run_batch=args.run_batch,
        dry_run=args.dry_run,
        strict_local_data=args.strict_local_data,
    )
    print(f"mode={result.mode}")
    print(f"status={result.status}")
    print(f"steps={len(result.steps)} warnings={len(result.warnings)}")
    print(f"markdown={result.report_markdown_path}")
    print(f"json={result.report_json_path}")
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
