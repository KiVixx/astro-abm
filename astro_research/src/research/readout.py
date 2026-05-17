from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from research.event_study_v2 import validate_exploratory_batch_outputs

TRACKED_HYPOTHESES = (
    "H001_station_cluster_stress",
    "H002_mercury_station_volatility",
    "H003_mars_saturn_hard_aspects",
    "H004_macro_core_aspect_cluster",
)


def build_research_readout(
    *,
    casebook_index_path: str | Path,
    batch_output_dir: str | Path,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        research_readout_markdown(
            casebook_index_path=casebook_index_path,
            batch_output_dir=batch_output_dir,
            readout_path=output,
        )
    )
    return output


def research_readout_markdown(
    *,
    casebook_index_path: str | Path,
    batch_output_dir: str | Path,
    readout_path: str | Path | None = None,
) -> str:
    casebook_path = Path(casebook_index_path)
    batch_dir = Path(batch_output_dir)
    results = _read_results(batch_dir)
    manifest = _read_json(batch_dir / "run_manifest.json")
    warnings_payload = _read_json(batch_dir / "warnings.json")
    validation_warnings = validate_exploratory_batch_outputs(batch_dir)
    top_findings_text = _read_text(batch_dir / "top_findings.md")
    case_count = _casebook_case_count(casebook_path)
    warning_categories = _warning_categories(warnings_payload)
    no_robust_findings = "No robust findings under current thresholds" in top_findings_text
    top_finding_rows = _markdown_table_row_count(top_findings_text)

    lines = [
        "# Research Readout",
        "",
        "This readout connects the descriptive crisis casebook index with the H001-H004 exploratory batch outputs. It is for historical association review only and does not assert causality, prediction, investment advice, or a trading signal.",
        "",
        "## Output Status",
        "",
        "| component | status | detail |",
        "|---|---|---|",
        f"| crisis_casebook_index | {_status(casebook_path.exists())} | cases={case_count}; path={_display_path(casebook_path)} |",
        f"| exploratory_batch | {_status(batch_dir.exists())} | rows={len(results)}; path={_display_path(batch_dir)} |",
        f"| run_manifest | {_status(bool(manifest))} | run_id={_manifest_value(manifest, 'run_id')}; run_type={_manifest_value(manifest, 'run_type')} |",
        f"| top_findings | {_status(bool(top_findings_text))} | no_robust_findings={str(no_robust_findings).lower()}; table_rows={top_finding_rows} |",
        "",
        "## Run Manifest",
        "",
        "| field | value |",
        "|---|---|",
        f"| manifest_version | {_manifest_value(manifest, 'manifest_version')} |",
        f"| run_id | {_manifest_value(manifest, 'run_id')} |",
        f"| config_sha256 | {_manifest_config_sha(manifest)} |",
        f"| git_commit | {_manifest_git_value(manifest, 'commit')} |",
        f"| git_dirty | {_manifest_git_value(manifest, 'dirty')} |",
        f"| readiness_status | {_manifest_readiness_value(manifest, 'status')} |",
        f"| input_rows | {_manifest_input_rows(manifest)} |",
        f"| output_artifacts | {_manifest_output_artifacts(manifest)} |",
        f"| manifest_warnings | {_manifest_warning_count(manifest)} |",
        "",
        "## H001-H004 Exploratory Batch",
        "",
        "| hypothesis | rows | sample_warnings | coverage_warnings |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(_hypothesis_rows(results))
    lines.extend(
        [
            "",
            "## Finding Status",
            "",
            f"- top_findings_available: `{str(bool(top_findings_text)).lower()}`",
            f"- no_robust_findings_under_current_thresholds: `{str(no_robust_findings).lower()}`",
            "- interpretation: descriptive exploratory summary only; no causal or operational conclusion is made.",
            "",
            "## Readiness Caveats",
            "",
            f"- readiness_status: `{_manifest_readiness_value(manifest, 'status')}`",
            f"- readiness_warning_counts: `{_readiness_warning_counts(manifest)}`",
            f"- warnings_json_categories: `{_counter_text(warning_categories)}`",
            f"- validation_warning_count: `{len(validation_warnings)}`",
        ]
    )
    if validation_warnings:
        lines.append(f"- validation_warnings: `{'; '.join(validation_warnings[:5])}`")
    if readout_path is not None:
        lines.append(f"- generated_readout: `{_display_path(Path(readout_path))}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Use this readout as a navigation layer across generated research artifacts. It does not make causal claims, predictions, trading signals, investment advice, or publication-grade claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def _read_results(batch_dir: Path) -> pd.DataFrame:
    csv_path = batch_dir / "results.csv"
    parquet_path = batch_dir / "results.parquet"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _casebook_case_count(path: Path) -> int:
    return _markdown_table_row_count(_read_text(path))


def _markdown_table_row_count(text: str) -> int:
    rows = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0].lower() in {"crisis", "hypothesis"}:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells if cell):
            continue
        rows += 1
    return rows


def _hypothesis_rows(results: pd.DataFrame) -> list[str]:
    rows = []
    for hypothesis in TRACKED_HYPOTHESES:
        subset = results[results["hypothesis_id"].astype(str) == hypothesis] if "hypothesis_id" in results.columns else pd.DataFrame()
        rows.append(
            f"| {hypothesis} | {len(subset)} | {_nonempty_count(subset, 'sample_warning')} | {_nonempty_count(subset, 'coverage_warning')} |"
        )
    return rows


def _nonempty_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    values = frame[column].fillna("").astype(str).str.strip()
    return int((values != "").sum())


def _warning_categories(payload: dict[str, Any]) -> Counter[str]:
    warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
    counts: Counter[str] = Counter()
    for item in warnings if isinstance(warnings, list) else []:
        if isinstance(item, dict):
            counts[str(item.get("category", "unknown"))] += 1
        else:
            counts["unknown"] += 1
    return counts


def _manifest_value(manifest: dict[str, Any], key: str) -> str:
    value = manifest.get(key, "missing") if isinstance(manifest, dict) else "missing"
    return _pipe_safe(value)


def _manifest_config_sha(manifest: dict[str, Any]) -> str:
    config = manifest.get("config", {}) if isinstance(manifest.get("config", {}), dict) else {}
    return _pipe_safe(config.get("sha256", "missing"))


def _manifest_git_value(manifest: dict[str, Any], key: str) -> str:
    git = manifest.get("git", {}) if isinstance(manifest.get("git", {}), dict) else {}
    return _pipe_safe(git.get(key, "missing"))


def _manifest_readiness_value(manifest: dict[str, Any], key: str) -> str:
    readiness = manifest.get("readiness", {}) if isinstance(manifest.get("readiness", {}), dict) else {}
    return _pipe_safe(readiness.get(key, "missing"))


def _manifest_input_rows(manifest: dict[str, Any]) -> str:
    inputs = manifest.get("inputs", []) if isinstance(manifest.get("inputs", []), list) else []
    rows = []
    for item in inputs:
        if isinstance(item, dict):
            rows.append(f"{item.get('name', 'unknown')}={item.get('row_count', 'unknown')}")
    return _pipe_safe(";".join(rows) if rows else "missing")


def _manifest_output_artifacts(manifest: dict[str, Any]) -> str:
    outputs = manifest.get("outputs", []) if isinstance(manifest.get("outputs", []), list) else []
    artifacts = [str(item.get("artifact", "unknown")) for item in outputs if isinstance(item, dict)]
    return _pipe_safe(";".join(artifacts) if artifacts else "missing")


def _manifest_warning_count(manifest: dict[str, Any]) -> str:
    warnings = manifest.get("warnings", {}) if isinstance(manifest.get("warnings", {}), dict) else {}
    return _pipe_safe(warnings.get("warning_count", "missing"))


def _readiness_warning_counts(manifest: dict[str, Any]) -> str:
    readiness = manifest.get("readiness", {}) if isinstance(manifest.get("readiness", {}), dict) else {}
    counts = readiness.get("warning_counts", {}) if isinstance(readiness.get("warning_counts", {}), dict) else {}
    return _counter_text(Counter({str(key): int(value) for key, value in counts.items()})) if counts else "missing"


def _counter_text(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ";".join(f"{key}={counter[key]}" for key in sorted(counter))


def _status(ok: bool) -> str:
    return "present" if ok else "missing"


def _display_path(path: Path) -> str:
    try:
        display = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        display = path
    return _pipe_safe(display.as_posix())


def _pipe_safe(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()
