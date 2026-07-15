from __future__ import annotations

import json
import logging
import os
import re
import stat
import tempfile
from pathlib import Path

from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.models.scenario import ScenarioSummary


SCENARIO_OUTPUT_DIR_ENV = "ASTRO_ABM_SCENARIO_OUTPUT_DIR"
SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
logger = logging.getLogger(__name__)


class ScenarioNotFoundError(FileNotFoundError):
    pass


class ScenarioUnreadableError(RuntimeError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(f"scenario report is unreadable ({category})")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_output_dir() -> Path:
    configured = os.getenv(SCENARIO_OUTPUT_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return repo_root() / "astro_research" / "output" / "scenarios"


def validate_scenario_id(scenario_id: str) -> str:
    if not SCENARIO_ID_PATTERN.fullmatch(scenario_id):
        raise ValueError("scenario_id may only contain lowercase letters, numbers, hyphens, and underscores")
    return scenario_id


def _atomic_write_text(path: Path, content: str) -> None:
    """Commit a complete UTF-8 file without exposing a partially written target."""
    existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if existing_mode is not None:
            temporary.chmod(existing_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _report_read_error_category(error: Exception) -> str:
    if isinstance(error, json.JSONDecodeError):
        return "invalid_json"
    if isinstance(error, UnicodeError):
        return "invalid_encoding"
    if isinstance(error, OSError):
        return "read_error"
    return "invalid_report_schema"


def report_to_summary(report: ScenarioReport) -> ScenarioSummary:
    worldline = report.worldline_simulation
    provenance = worldline.provenance if worldline else {}
    provenance_mode = provenance.get("generation_mode")
    generation_mode = (
        provenance_mode
        if isinstance(provenance_mode, str) and provenance_mode
        else worldline.mode if worldline else None
    )
    failed_chunk_count = provenance.get("failed_chunk_count", 0)
    coverage = report.coverage_summary
    return ScenarioSummary(
        scenario_id=report.scenario_id,
        title=report.title,
        description=report.description,
        created_at=report.created_at,
        start_date=report.start_date,
        end_date=report.end_date,
        assets=report.assets,
        agent_ids=[agent.agent_id for agent in report.agents],
        agent_names=[agent.name for agent in report.agents],
        visibility=report.visibility,
        mode=report.mode,
        language=report.language,
        worldline_status=worldline.status if worldline else None,
        worldline_generation_mode=generation_mode,
        worldline_day_count=worldline.horizon_days if worldline else 0,
        worldline_failed_chunk_count=(
            int(failed_chunk_count) if isinstance(failed_chunk_count, (int, float)) else 0
        ),
        llm_report_status=report.llm_report.status if report.llm_report else None,
        coverage_total_days=coverage.total_days if coverage else None,
        coverage_local_research_days=coverage.local_research_days if coverage else None,
        coverage_future_placeholder_days=coverage.future_placeholder_days if coverage else None,
    )


class ScenarioStore:
    def __init__(self, output_dir: Path | str | None = None) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve() if output_dir else default_output_dir()

    def ensure_output_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, scenario_id: str, suffix: str) -> Path:
        validate_scenario_id(scenario_id)
        if suffix not in {".json", ".md"}:
            raise ValueError("scenario store only supports .json and .md files")
        path = (self.output_dir / f"{scenario_id}{suffix}").resolve()
        if path.parent != self.output_dir:
            raise ValueError("scenario path must stay inside the scenario output directory")
        return path

    def save(self, report: ScenarioReport) -> ScenarioReport:
        self.ensure_output_dir()
        json_path = self._path_for(report.scenario_id, ".json")
        markdown_path = self._path_for(report.scenario_id, ".md")
        _atomic_write_text(json_path, report.model_dump_json(indent=2))
        _atomic_write_text(markdown_path, report.markdown_report)
        return report

    def load(self, scenario_id: str) -> ScenarioReport:
        json_path = self._path_for(scenario_id, ".json")
        if not json_path.exists():
            raise ScenarioNotFoundError(scenario_id)
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            return ScenarioReport.model_validate(data)
        except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
            category = _report_read_error_category(error)
            logger.warning(
                "Unable to load scenario report %s (%s)",
                json_path.name,
                category,
            )
            raise ScenarioUnreadableError(category) from error

    def delete(self, scenario_id: str) -> None:
        json_path = self._path_for(scenario_id, ".json")
        markdown_path = self._path_for(scenario_id, ".md")
        if not json_path.exists():
            raise ScenarioNotFoundError(scenario_id)
        json_path.unlink()
        if markdown_path.exists():
            markdown_path.unlink()

    def list_summaries(self) -> list[ScenarioSummary]:
        if not self.output_dir.exists():
            return []

        summaries: list[ScenarioSummary] = []
        for json_path in sorted(self.output_dir.glob("*.json")):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                report = ScenarioReport.model_validate(data)
            except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
                logger.warning(
                    "Skipping unreadable scenario report %s (%s)",
                    json_path.name,
                    _report_read_error_category(error),
                )
                continue
            summaries.append(report_to_summary(report))
        return sorted(summaries, key=lambda item: item.created_at, reverse=True)
