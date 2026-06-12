from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class MaintenanceTaskResult:
    name: str
    status: str
    rows_written: int = 0
    skipped_existing: int = 0
    errors: tuple[str, ...] = ()
    details: str = ""


@dataclass(frozen=True)
class MaintenanceSummary:
    run_ts: datetime
    window_start: datetime
    window_end: datetime
    tasks: tuple[MaintenanceTaskResult, ...]

    @property
    def failed(self) -> bool:
        return any(task.status == "failed" for task in self.tasks)

    @property
    def partial(self) -> bool:
        return any(task.status == "partial" for task in self.tasks)

    @property
    def rows_written(self) -> int:
        return sum(task.rows_written for task in self.tasks)

    @property
    def skipped_existing(self) -> int:
        return sum(task.skipped_existing for task in self.tasks)


def run_maintenance_tasks(tasks: Iterable[tuple[str, Callable[[], object]]]) -> tuple[MaintenanceTaskResult, ...]:
    results: list[MaintenanceTaskResult] = []
    for name, task_func in tasks:
        try:
            summary = task_func()
        except Exception as exc:
            results.append(
                MaintenanceTaskResult(
                    name=name,
                    status="failed",
                    errors=(f"{type(exc).__name__}:{exc}",),
                )
            )
            continue
        results.append(_task_result_from_summary(name, summary))
    return tuple(results)


def format_maintenance_summary(summary: MaintenanceSummary, *, title: str) -> str:
    lines = [
        title,
        f"run_ts={summary.run_ts.isoformat()}",
        f"window={summary.window_start.isoformat()} -> {summary.window_end.isoformat()}",
        f"rows_written={summary.rows_written} skipped_existing={summary.skipped_existing}",
        "",
        "Tasks",
    ]
    for task in summary.tasks:
        line = (
            f"  - {task.name}: status={task.status} rows={task.rows_written} "
            f"skipped={task.skipped_existing} errors={len(task.errors)}"
        )
        if task.details:
            line += f" details={task.details}"
        lines.append(line)
        for error in task.errors[:5]:
            lines.append(f"    error: {error}")
    return "\n".join(lines)


def split_symbols(value: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    return tuple(item.strip().upper() for item in values if item and item.strip())


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _task_result_from_summary(name: str, summary: object) -> MaintenanceTaskResult:
    errors = tuple(getattr(summary, "errors", ()) or ())
    status = "success" if not errors else "partial" if _summary_int(summary, "written", "rows_written") else "failed"
    return MaintenanceTaskResult(
        name=name,
        status=status,
        rows_written=_summary_int(summary, "written", "rows_written"),
        skipped_existing=_summary_int(summary, "skipped_existing"),
        errors=errors,
        details=_summary_details(summary),
    )


def _summary_int(summary: object, *names: str) -> int:
    for name in names:
        if hasattr(summary, name):
            return int(getattr(summary, name) or 0)
    return 0


def _summary_details(summary: object) -> str:
    parts = []
    for name in (
        "fetched",
        "fetched_files",
        "missing_files",
        "records_seen",
        "hours_seen",
        "years_seen",
        "read_bars",
        "mode",
        "steps_seen",
        "warnings_seen",
        "report_json_path",
    ):
        if hasattr(summary, name):
            parts.append(f"{name}={getattr(summary, name)}")
    run_id = getattr(summary, "run_id", None)
    if run_id:
        parts.append(f"run_id={run_id}")
    return " ".join(parts)
