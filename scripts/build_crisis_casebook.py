#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.casebook import build_casebook


def main() -> int:
    parser = argparse.ArgumentParser(description="Build descriptive crisis casebook reports.")
    parser.add_argument("--config", default="astro_research/configs/crisis_casebook.yaml")
    parser.add_argument("--output", default="astro_research/output/reports/casebook")
    args = parser.parse_args()
    paths = build_casebook(ROOT / args.config, root=ROOT, output_dir=ROOT / args.output)
    print(f"case_reports={len(paths)} output={ROOT / args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
