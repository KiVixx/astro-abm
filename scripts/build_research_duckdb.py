#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.full_history_store import DUCKDB_OUTPUT, build_duckdb_store, discover_snapshot_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the full-history DuckDB research store from ignored snapshots.")
    parser.add_argument("--snapshot-root", default="astro_research/output/parquet")
    parser.add_argument("--output", default=str(DUCKDB_OUTPUT))
    parser.add_argument("--skip-aspect-chunks", action="store_true")
    parser.add_argument("--no-overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Only list discovered inputs.")
    args = parser.parse_args()

    snapshot_root = ROOT / args.snapshot_root
    output = ROOT / args.output
    sources = discover_snapshot_sources(snapshot_root, include_aspect_chunks=not args.skip_aspect_chunks)
    print(f"snapshot_root={snapshot_root}")
    print(f"discovered_tables={len(sources)}")
    for source in sources:
        print(f"source={source.table_name} format={source.source_format} files={len(source.paths)}")
    if args.dry_run:
        print("dry_run=true")
        return 0

    result = build_duckdb_store(
        snapshot_root=snapshot_root,
        output_path=output,
        include_aspect_chunks=not args.skip_aspect_chunks,
        overwrite=not args.no_overwrite,
    )
    pre_1970_tables = result.manifest[result.manifest["includes_pre_1970"]]["table_name"].tolist()
    print(f"output={result.output_path}")
    print(f"tables={len(result.manifest)}")
    print(f"pre_1970_tables={pre_1970_tables}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
