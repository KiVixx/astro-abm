from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable, Sequence


LOCAL_DATA_FILES = {
    "SPX": Path("astro_research/data/local/equity/spx_daily.csv"),
    "Gold": Path("astro_research/data/local/commodities/gold_daily.csv"),
    "DXY": Path("astro_research/data/local/fx/dxy_daily.csv"),
    "CreditProxy": Path("astro_research/data/local/credit/hy_oas_daily.csv"),
}

DEFAULT_PUBLIC_RUN_ID = "research_prepare_public"
DEFAULT_FORMAL_RUN_ID = "exploratory_formal_batch_v1_1926_2025"


@dataclass(frozen=True)
class ResearchPrepareStep:
    name: str
    status: str
    detail: str = ""
    command: tuple[str, ...] = ()
    returncode: int | None = None


@dataclass(frozen=True)
class ResearchPrepareResult:
    mode: str
    status: str
    started_at: str
    finished_at: str
    report_markdown_path: Path
    report_json_path: Path
    steps: tuple[ResearchPrepareStep, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def failed(self) -> bool:
        return self.status == "failed"


Runner = Callable[[Sequence[str]], object]


def prepare_research(
    *,
    root: str | Path,
    mode: str = "public",
    start: str = "1926-01-01",
    end: str | None = None,
    aspect_profile: str = "macro_core",
    workers: int = 1,
    ingest: bool = False,
    run_batch: bool = False,
    dry_run: bool = False,
    strict_local_data: bool = False,
    runner: Runner | None = None,
) -> ResearchPrepareResult:
    root_path = Path(root)
    if mode not in {"public", "local-full", "formal"}:
        raise ValueError(f"Unsupported research prepare mode: {mode}")

    end = end or date.today().isoformat()
    started_at = _utc_now()
    steps: list[ResearchPrepareStep] = []
    warnings: list[str] = []
    run = runner or (lambda command: subprocess.run(list(command), cwd=root_path, check=False))

    steps.extend(_local_data_steps(root_path=root_path, mode=mode, strict=strict_local_data))
    warnings.extend(step.detail for step in steps if step.status == "warning")
    if any(step.status == "failed" for step in steps):
        result = _finish_result(mode, started_at, root_path, steps, warnings)
        _write_reports(result)
        return result

    for command_step in _command_plan(
        mode=mode,
        start=start,
        end=end,
        aspect_profile=aspect_profile,
        workers=workers,
        ingest=ingest,
        run_batch=run_batch,
    ):
        if dry_run:
            steps.append(
                ResearchPrepareStep(
                    name=command_step.name,
                    status="skipped",
                    detail="dry-run; command not executed",
                    command=command_step.command,
                )
            )
            continue
        step = _run_command_step(command_step, run)
        steps.append(step)
        if step.status == "failed":
            warnings.append(f"{step.name}: failed with returncode={step.returncode}")
            break

    result = _finish_result(mode, started_at, root_path, steps, warnings)
    _write_reports(result)
    return result


def _command_plan(
    *,
    mode: str,
    start: str,
    end: str,
    aspect_profile: str,
    workers: int,
    ingest: bool,
    run_batch: bool,
) -> tuple[ResearchPrepareStep, ...]:
    commands: list[ResearchPrepareStep] = []
    ingest_flag = ("--ingest",) if ingest else ()
    market_command = [
        "uv",
        "run",
        "python",
        "scripts/build_market_daily.py",
        "--config",
        "astro_research/configs/market_assets_real.yaml",
        "--start",
        start,
        "--end",
        end,
        "--write-parquet",
        "astro_research/output/parquet/market_daily",
    ]
    if mode == "public":
        market_command.extend(["--source", "fred"])
    commands.extend(
        (
            _command(
                "source_registry",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_data_source_registry.py",
                    "--config",
                    "astro_research/configs/data_sources.yaml",
                    "--write-parquet",
                    "astro_research/output/parquet/source_registry",
                    "--output",
                    "astro_research/output/reports/source_registry.md",
                    *ingest_flag,
                ],
            ),
            _command("market_daily", [*market_command, *ingest_flag]),
            _command(
                "macro_daily",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_macro_daily.py",
                    "--config",
                    "astro_research/configs/macro_series.yaml",
                    "--start",
                    start,
                    "--end",
                    end,
                    "--write-parquet",
                    "astro_research/output/parquet/macro_daily",
                    *ingest_flag,
                ],
            ),
            _command(
                "financial_stress_daily",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_financial_stress_daily.py",
                    "--config",
                    "astro_research/configs/financial_stress.yaml",
                    "--write-parquet",
                    "astro_research/output/parquet/financial_stress",
                    *ingest_flag,
                ],
            ),
            _command(
                "formal_readiness",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/build_formal_research_readiness.py",
                ],
            ),
        )
    )

    if mode == "formal":
        commands.extend(
            (
                _command(
                    "aspect_chunks",
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/build_astro_daily.py",
                        "--config",
                        "astro_research/configs/astro_daily.yaml",
                        "--aspect-profile",
                        aspect_profile,
                        "--aspect-start",
                        "1926-01-01",
                        "--aspect-end",
                        "2025-12-31",
                        "--write-parquet",
                        f"astro_research/output/parquet/aspect_chunks_mvp35/{aspect_profile}_1926_2025",
                        "--skip-existing",
                        "--resume",
                        "--workers",
                        str(max(1, workers)),
                    ],
                ),
                _command(
                    "research_events",
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/build_research_events.py",
                        "--config",
                        "astro_research/configs/research_events.yaml",
                        "--write-parquet",
                        "astro_research/output/parquet/research_events",
                        *ingest_flag,
                    ],
                ),
                _command(
                    "research_hypotheses",
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/register_hypotheses.py",
                        "--config",
                        "astro_research/configs/research_hypotheses.yaml",
                        "--git-commit",
                        "auto",
                        "--write-parquet",
                        "astro_research/output/parquet/research_hypotheses",
                        *ingest_flag,
                    ],
                ),
            )
        )
        if run_batch:
            commands.append(
                _command(
                    "exploratory_formal_batch",
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/run_research_batch.py",
                        "--config",
                        "astro_research/configs/research_batch_exploratory_v1.yaml",
                        "--run-id",
                        DEFAULT_FORMAL_RUN_ID,
                        "--output",
                        f"astro_research/output/reports/{DEFAULT_FORMAL_RUN_ID}",
                        *ingest_flag,
                    ],
                )
            )

    commands.append(
        _command(
            "duckdb_research_store",
            [
                "uv",
                "run",
                "python",
                "scripts/build_research_duckdb.py",
                "--snapshot-root",
                "astro_research/output/parquet",
                "--output",
                "astro_research/output/duckdb/astro_research_full_history.duckdb",
            ],
        )
    )
    commands.append(_validation_command(run_batch=run_batch and mode == "formal"))
    return tuple(commands)


def _validation_command(*, run_batch: bool) -> ResearchPrepareStep:
    command = [
        "uv",
        "run",
        "python",
        "scripts/validate_research_layer.py",
        "--output",
        "astro_research/output/reports/research_layer_validation.md",
    ]
    if run_batch:
        report_dir = f"astro_research/output/reports/{DEFAULT_FORMAL_RUN_ID}"
        command.extend(
            [
                "--event-study-results",
                f"{report_dir}/results.parquet",
                "--event-traceability",
                f"{report_dir}/event_traceability.csv",
                "--run-manifest",
                f"{report_dir}/run_manifest.json",
            ]
        )
    return _command("research_layer_validation", command)


def _command(name: str, command: Sequence[str]) -> ResearchPrepareStep:
    return ResearchPrepareStep(name=name, status="pending", command=tuple(str(part) for part in command))


def _run_command_step(step: ResearchPrepareStep, runner: Runner) -> ResearchPrepareStep:
    print("$ " + " ".join(step.command), flush=True)
    completed = runner(step.command)
    returncode = int(getattr(completed, "returncode", completed))
    return ResearchPrepareStep(
        name=step.name,
        status="completed" if returncode == 0 else "failed",
        detail="" if returncode == 0 else f"command failed: returncode={returncode}",
        command=step.command,
        returncode=returncode,
    )


def _local_data_steps(*, root_path: Path, mode: str, strict: bool) -> list[ResearchPrepareStep]:
    if mode == "public":
        return [
            ResearchPrepareStep(
                name="local_data_policy",
                status="completed",
                detail="public mode skips private local CSV requirements",
            )
        ]
    missing = [label for label, rel_path in LOCAL_DATA_FILES.items() if not (root_path / rel_path).exists()]
    if not missing:
        return [
            ResearchPrepareStep(
                name="local_data_check",
                status="completed",
                detail="all optional long-history local CSV files are present",
            )
        ]
    detail = "missing optional long-history local CSV: " + ", ".join(missing)
    return [
        ResearchPrepareStep(
            name="local_data_check",
            status="failed" if strict else "warning",
            detail=detail,
        )
    ]


def _finish_result(
    mode: str,
    started_at: str,
    root_path: Path,
    steps: list[ResearchPrepareStep],
    warnings: list[str],
) -> ResearchPrepareResult:
    failed = any(step.status == "failed" for step in steps)
    warning = bool(warnings) or any(step.status == "warning" for step in steps)
    status = "failed" if failed else "completed_with_warnings" if warning else "completed"
    output = root_path / "astro_research/output/reports"
    return ResearchPrepareResult(
        mode=mode,
        status=status,
        started_at=started_at,
        finished_at=_utc_now(),
        report_markdown_path=output / f"research_prepare_{mode}.md",
        report_json_path=output / f"research_prepare_{mode}.json",
        steps=tuple(steps),
        warnings=tuple(warnings),
    )


def _write_reports(result: ResearchPrepareResult) -> None:
    result.report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    result.report_markdown_path.write_text(_markdown(result))
    payload = asdict(result)
    payload["report_markdown_path"] = str(result.report_markdown_path)
    payload["report_json_path"] = str(result.report_json_path)
    result.report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _markdown(result: ResearchPrepareResult) -> str:
    lines = [
        f"# Research Prepare Report: {result.mode}",
        "",
        f"- status: `{result.status}`",
        f"- started_at: `{result.started_at}`",
        f"- finished_at: `{result.finished_at}`",
        "",
        "## Steps",
        "",
        "| step | status | returncode | detail |",
        "|---|---:|---:|---|",
    ]
    for step in result.steps:
        detail = step.detail.replace("|", "\\|") if step.detail else ""
        returncode = "" if step.returncode is None else str(step.returncode)
        lines.append(f"| `{step.name}` | `{step.status}` | {returncode} | {detail} |")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.extend(
        [
            "",
            "## Mode Notes",
            "",
            "- `public`: public/API data plus DuckDB readiness; does not require private local CSV files.",
            "- `local-full`: includes optional long-history local CSV sources when present.",
            "- `formal`: adds expensive macro-core aspect chunks, normalized research events, hypotheses, and optional exploratory batch.",
        ]
    )
    return "\n".join(lines) + "\n"


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()
