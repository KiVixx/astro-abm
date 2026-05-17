#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.readout import build_research_readout


def main() -> int:
    parser = argparse.ArgumentParser(description="Build descriptive research readout across casebook and exploratory batch outputs.")
    parser.add_argument("--casebook-index", default="astro_research/output/reports/casebook/index.md")
    parser.add_argument("--batch-output", default="astro_research/output/reports/exploratory_formal_batch_v1_resume_smoke")
    parser.add_argument("--output", default="astro_research/output/reports/research_readout/readout.md")
    args = parser.parse_args()

    path = build_research_readout(
        casebook_index_path=ROOT / args.casebook_index,
        batch_output_dir=ROOT / args.batch_output,
        output_path=ROOT / args.output,
    )
    print(f"research_readout={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
