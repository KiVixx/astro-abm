#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "astro_research" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from research.casebook import build_casebook
from research.event_study_v2 import run_research_batch, validate_exploratory_batch_outputs, write_batch_report
from research.io import read_table
from research.readout import build_research_readout

OUTPUT_ROOT = ROOT / "astro_research" / "output"
SECRET_PATTERN = re.compile(
    r"AKIA[0-9A-Z]{16}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY"
    r"|api[_-]?key\s*[=:]"
    r"|secret[_-]?key\s*[=:]"
    r"|access[_-]?token\s*[=:]"
    r"|password\s*[=:]"
    r"|connection[_-]?string\s*[=:]",
    re.IGNORECASE,
)
FORBIDDEN_OPERATIONAL_PHRASES = (
    "causes market",
    "caused market",
    "predicts market",
    "predicts stress",
    "buy signal",
    "sell signal",
    "investment advice:",
)
REQUIRED_BOUNDARY = "does not assert causality, prediction, investment advice, or a trading signal"


@dataclass(frozen=True)
class WorkflowPaths:
    casebook_output: Path
    batch_output: Path
    readout_output: Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the descriptive research workflow checkpoint.")
    parser.add_argument("--casebook-config", default="astro_research/configs/crisis_casebook.yaml")
    parser.add_argument("--batch-config", default="astro_research/configs/research_batch_exploratory_v1.yaml")
    parser.add_argument("--casebook-output", default="astro_research/output/reports/research_workflow_checkpoint/casebook")
    parser.add_argument("--batch-output", default="astro_research/output/reports/research_workflow_checkpoint/exploratory_batch")
    parser.add_argument("--readout-output", default="astro_research/output/reports/research_workflow_checkpoint/readout.md")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--check-only", action="store_true", help="Skip regeneration and only validate existing checkpoint outputs.")
    args = parser.parse_args()

    paths = WorkflowPaths(
        casebook_output=_resolve(args.casebook_output),
        batch_output=_resolve(args.batch_output),
        readout_output=_resolve(args.readout_output),
    )
    warnings: list[str] = []
    if not args.check_only:
        _run_workflow(
            casebook_config=_resolve(args.casebook_config),
            batch_config=_resolve(args.batch_config),
            paths=paths,
            run_id=args.run_id,
        )
    warnings.extend(validate_checkpoint(paths))

    print(f"casebook_index={paths.casebook_output / 'index.md'}")
    print(f"batch_output={paths.batch_output}")
    print(f"research_readout={paths.readout_output}")
    print(f"checkpoint_warnings={len(warnings)}")
    for warning in warnings:
        print(f"checkpoint_warning={warning}")
    return 1 if warnings else 0


def validate_checkpoint(paths: WorkflowPaths) -> list[str]:
    warnings: list[str] = []
    for label, path in {
        "casebook_output": paths.casebook_output,
        "batch_output": paths.batch_output,
        "readout_output": paths.readout_output,
    }.items():
        if not _is_under_output(path):
            warnings.append(f"{label}: outside astro_research/output")

    if not (paths.casebook_output / "index.md").exists():
        warnings.append("casebook_index: missing")
    if not (paths.batch_output / "run_manifest.json").exists():
        warnings.append("run_manifest: missing")
    if not paths.readout_output.exists():
        warnings.append("research_readout: missing")
    else:
        warnings.extend(_language_warnings(paths.readout_output.read_text()))

    warnings.extend(validate_exploratory_batch_outputs(paths.batch_output))
    warnings.extend(_staged_boundary_warnings())
    return warnings


def _run_workflow(*, casebook_config: Path, batch_config: Path, paths: WorkflowPaths, run_id: str | None) -> None:
    build_casebook(casebook_config, root=ROOT, output_dir=paths.casebook_output)
    batch = run_research_batch(batch_config, root=ROOT, run_id_override=run_id)
    hypothesis_snapshot = _hypothesis_snapshot()
    write_batch_report(batch, paths.batch_output, config_text=batch_config.read_text(), hypothesis_snapshot=hypothesis_snapshot)
    build_research_readout(
        casebook_index_path=paths.casebook_output / "index.md",
        batch_output_dir=paths.batch_output,
        output_path=paths.readout_output,
    )


def _hypothesis_snapshot():
    parquet_path = ROOT / "astro_research/output/parquet/research_hypotheses/research_hypotheses.parquet"
    csv_path = ROOT / "astro_research/output/parquet/research_hypotheses/research_hypotheses.csv"
    return read_table(parquet_path) if parquet_path.exists() else read_table(csv_path)


def _language_warnings(text: str) -> list[str]:
    lowered = text.lower()
    warnings = []
    if REQUIRED_BOUNDARY not in lowered:
        warnings.append("research_readout: missing descriptive-only boundary")
    for phrase in FORBIDDEN_OPERATIONAL_PHRASES:
        if phrase in lowered:
            warnings.append(f"research_readout: forbidden operational phrase `{phrase}`")
    return warnings


def _staged_boundary_warnings() -> list[str]:
    staged = _git(["diff", "--cached", "--name-only"])
    warnings = []
    for name in staged.splitlines():
        if name.startswith("astro_research/output/"):
            warnings.append(f"staged generated output: {name}")
        if name.startswith("astro_research/data/local/") and name.endswith(".csv"):
            warnings.append(f"staged local csv: {name}")
    staged_diff = _git(["diff", "--cached"])
    if SECRET_PATTERN.search(staged_diff):
        warnings.append("staged diff: possible secret or credential pattern")
    return warnings


def _git(args: list[str]) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return completed.stdout


def _is_under_output(path: Path) -> bool:
    try:
        path.resolve().relative_to(OUTPUT_ROOT.resolve())
    except ValueError:
        return False
    return True


def _resolve(path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else ROOT / target


if __name__ == "__main__":
    raise SystemExit(main())
