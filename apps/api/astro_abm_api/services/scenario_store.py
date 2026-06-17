from __future__ import annotations

import json
import os
import re
from pathlib import Path

from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.models.scenario import ScenarioSummary


SCENARIO_OUTPUT_DIR_ENV = "ASTRO_ABM_SCENARIO_OUTPUT_DIR"
SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")


class ScenarioNotFoundError(FileNotFoundError):
    pass


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


def report_to_summary(report: ScenarioReport) -> ScenarioSummary:
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
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        markdown_path.write_text(report.markdown_report, encoding="utf-8")
        return report

    def load(self, scenario_id: str) -> ScenarioReport:
        json_path = self._path_for(scenario_id, ".json")
        if not json_path.exists():
            raise ScenarioNotFoundError(scenario_id)
        return ScenarioReport.model_validate_json(json_path.read_text(encoding="utf-8"))

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
            except (json.JSONDecodeError, OSError, ValueError):
                continue
            summaries.append(report_to_summary(report))
        return sorted(summaries, key=lambda item: item.created_at, reverse=True)
