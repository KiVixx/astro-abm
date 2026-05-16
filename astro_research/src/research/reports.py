from __future__ import annotations

from pathlib import Path

import pandas as pd

from research.config import EventStudyConfig


def write_event_study_report(*, results: pd.DataFrame, config: EventStudyConfig, output_dir: str | Path, config_text: str) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary.md": output / "summary.md",
        "results.csv": output / "results.csv",
        "results.parquet": output / "results.parquet",
        "config_snapshot.yaml": output / "config_snapshot.yaml",
    }
    results.to_csv(paths["results.csv"], index=False)
    results.to_parquet(paths["results.parquet"], index=False)
    paths["config_snapshot.yaml"].write_text(config_text)
    paths["summary.md"].write_text(_summary(results, config))
    return paths


def _summary(results: pd.DataFrame, config: EventStudyConfig) -> str:
    if results.empty:
        body = "No event study rows were produced.\n"
    else:
        top = results.sort_values("q_value_fdr", na_position="last").head(12)
        lines = [
            "| event_type | asset | window | metric | effect_minus_baseline | p_value | q_value_fdr | n_events |",
            "|---|---:|---|---|---:|---:|---:|---:|",
        ]
        for row in top.itertuples(index=False):
            lines.append(
                f"| {row.event_type} | {row.asset} | {row.window_name} | {row.metric} | "
                f"{row.effect_minus_baseline:.6g} | {row.p_value:.4g} | {row.q_value_fdr:.4g} | {row.n_events} |"
            )
        body = "\n".join(lines) + "\n"
    return (
        f"# Event Study Summary\n\n"
        f"run_id: `{config.run_id}`\n\n"
        f"Mode: calendar-day event study with non-event, month-matched, and weekday-matched baselines.\n\n"
        f"Rows: {len(results)}\n\n"
        f"## Top Results By FDR\n\n"
        f"{body}\n"
        f"## Caveats\n\n"
        f"- This is MVP4 v1. It validates the research plumbing before any claim of astro alpha.\n"
        f"- Placebo percentile is stored in `real_percentile_vs_placebo` and mirrored in `source_note` for table compatibility.\n"
    )
