from __future__ import annotations

import argparse
import json
from pathlib import Path

from astro_abm.marksix import public_sync_summary, sync_marksix


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or refresh the local Hong Kong Mark Six draw database.")
    parser.add_argument("--full", action="store_true", help="Refresh the complete configured historical archive.")
    parser.add_argument("--db-path", type=Path, default=None, help="Override the ignored local SQLite path.")
    args = parser.parse_args()
    summary = sync_marksix(full_history=True if args.full else None, path=args.db_path)
    print(json.dumps(public_sync_summary(summary), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
