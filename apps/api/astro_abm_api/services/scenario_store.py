from __future__ import annotations

import json
import logging
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from astro_abm_api.models.report import ScenarioReport, WorldlineSimulation
from astro_abm_api.models.scenario import ScenarioSummary
from astro_abm_api.services.simulation_engine import build_coverage_summary


SCENARIO_OUTPUT_DIR_ENV = "ASTRO_ABM_SCENARIO_OUTPUT_DIR"
SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
logger = logging.getLogger(__name__)


class ScenarioCapacityError(RuntimeError):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(f"scenario capacity unavailable ({category})")


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
    configuration_fallback_count, llm_failed_count = _summary_fallback_counts(
        provenance,
        failed_chunk_count,
    )
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
        worldline_playable_day_count=_playable_worldline_day_count(worldline),
        worldline_generation_halted=bool(provenance.get("generation_halted", False)),
        worldline_failed_chunk_count=(
            int(failed_chunk_count) if isinstance(failed_chunk_count, (int, float)) else 0
        ),
        worldline_configuration_fallback_chunk_count=configuration_fallback_count,
        worldline_llm_failed_chunk_count=llm_failed_count,
        llm_report_status=report.llm_report.status if report.llm_report else None,
        coverage_total_days=coverage.total_days if coverage else None,
        coverage_local_research_days=coverage.local_research_days if coverage else None,
        coverage_future_placeholder_days=coverage.future_placeholder_days if coverage else None,
    )


def _playable_worldline_day_count(worldline: WorldlineSimulation | None) -> int:
    if worldline is None:
        return 0
    provenance = worldline.provenance
    if not provenance.get("generation_halted"):
        return worldline.horizon_days
    chunk_history = provenance.get("chunk_history")
    if not isinstance(chunk_history, list):
        return worldline.horizon_days
    failed_chunk = next(
        (
            chunk
            for chunk in chunk_history
            if isinstance(chunk, dict)
            and chunk.get("status") == "fallback"
            and chunk.get("generation_halted") is True
        ),
        None,
    )
    if failed_chunk is None:
        return worldline.horizon_days
    end_date = failed_chunk.get("chunk_end_date")
    if not isinstance(end_date, str):
        return worldline.horizon_days
    return sum(1 for day in worldline.days if day.date.isoformat() <= end_date)


def _refresh_derived_coverage(report: ScenarioReport) -> ScenarioReport:
    if report.coverage_summary is None or not report.daily_timeline:
        return report
    coverage_summary = build_coverage_summary(
        report.daily_timeline,
        report.assets,
        created_at=report.created_at,
        language=report.language or "en",
    )
    return report.model_copy(update={"coverage_summary": coverage_summary})


def _summary_fallback_counts(
    provenance: dict[str, object],
    failed_chunk_count: object,
) -> tuple[int, int]:
    explicit_configuration = provenance.get("configuration_fallback_chunk_count")
    explicit_llm_failed = provenance.get("llm_failed_chunk_count")
    if isinstance(explicit_configuration, (int, float)) and isinstance(
        explicit_llm_failed,
        (int, float),
    ):
        return max(0, int(explicit_configuration)), max(0, int(explicit_llm_failed))

    configuration_count = 0
    llm_failed_count = 0
    history = provenance.get("chunk_history")
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict) or item.get("status") != "fallback":
                continue
            reason = item.get("fallback_reason")
            is_configuration = reason in {
                "unsupported_llm_provider",
                "real_llm_disabled",
                "llm_base_url_missing",
                "llm_model_missing",
                "legacy_configuration_unavailable",
            } or (
                not item.get("network_call_performed")
                and item.get("output_validation_status")
                in {
                    "configuration_missing",
                    "llm_disabled_or_config_unavailable",
                    "not_run",
                }
            )
            if is_configuration:
                configuration_count += 1
            else:
                llm_failed_count += 1
    if configuration_count or llm_failed_count:
        return configuration_count, llm_failed_count

    legacy_failed_count = (
        max(0, int(failed_chunk_count))
        if isinstance(failed_chunk_count, (int, float))
        else 0
    )
    return 0, legacy_failed_count


class ScenarioStore:
    def __init__(self, output_dir: Path | str | None = None) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve() if output_dir else default_output_dir()

    def ensure_output_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def storage_usage(self) -> dict[str, int]:
        if not self.output_dir.exists():
            return {"report_count": 0, "stored_bytes": 0}
        json_files = list(self.output_dir.glob("*.json"))
        data_files = [*json_files, *self.output_dir.glob("*.md")]
        return {
            "report_count": len(json_files),
            "stored_bytes": sum(path.stat().st_size for path in data_files if path.is_file()),
        }

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
        json_content = report.model_dump_json(indent=2)
        markdown_content = report.markdown_report
        with self._capacity_lock():
            self._enforce_capacity(
                json_path=json_path,
                markdown_path=markdown_path,
                json_bytes=len(json_content.encode("utf-8")),
                markdown_bytes=len(markdown_content.encode("utf-8")),
            )
            _atomic_write_text(json_path, json_content)
            _atomic_write_text(markdown_path, markdown_content)
        return report

    @contextmanager
    def _capacity_lock(self):  # type: ignore[no-untyped-def]
        lock_path = self.output_dir / ".scenario-capacity.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except (ImportError, NameError):
                    pass

    def _enforce_capacity(
        self,
        *,
        json_path: Path,
        markdown_path: Path,
        json_bytes: int,
        markdown_bytes: int,
    ) -> None:
        single_report_bytes = json_bytes + markdown_bytes
        if single_report_bytes > _capacity_env(
            "ASTRO_ABM_SCENARIO_MAX_REPORT_BYTES", 16 * 1024 * 1024, 64 * 1024
        ):
            raise ScenarioCapacityError("single_report_bytes")

        json_files = list(self.output_dir.glob("*.json"))
        is_new = not json_path.exists()
        if is_new and len(json_files) >= _capacity_env(
            "ASTRO_ABM_SCENARIO_STORE_MAX_REPORTS", 5000, 1
        ):
            raise ScenarioCapacityError("report_count")

        data_files = [*json_files, *self.output_dir.glob("*.md")]
        current_bytes = sum(path.stat().st_size for path in data_files if path.is_file())
        replaced_bytes = sum(
            path.stat().st_size for path in (json_path, markdown_path) if path.exists()
        )
        projected_bytes = current_bytes - replaced_bytes + single_report_bytes
        maximum_bytes = _capacity_env(
            "ASTRO_ABM_SCENARIO_STORE_MAX_BYTES", 2 * 1024 * 1024 * 1024, 1024 * 1024
        )
        if projected_bytes > maximum_bytes and projected_bytes > current_bytes:
            raise ScenarioCapacityError("store_bytes")

    def load(self, scenario_id: str) -> ScenarioReport:
        json_path = self._path_for(scenario_id, ".json")
        if not json_path.exists():
            raise ScenarioNotFoundError(scenario_id)
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            return _refresh_derived_coverage(ScenarioReport.model_validate(data))
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

    def list_summaries(self, limit: int | None = None) -> list[ScenarioSummary]:
        if not self.output_dir.exists():
            return []

        summaries: list[ScenarioSummary] = []
        scan_limit = _capacity_env("ASTRO_ABM_SCENARIO_LIST_SCAN_LIMIT", 1000, 1)
        json_paths = sorted(
            self.output_dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:scan_limit]
        for json_path in json_paths:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                report = _refresh_derived_coverage(ScenarioReport.model_validate(data))
            except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
                logger.warning(
                    "Skipping unreadable scenario report %s (%s)",
                    json_path.name,
                    _report_read_error_category(error),
                )
                continue
            summaries.append(report_to_summary(report))
        ordered = sorted(summaries, key=lambda item: item.created_at, reverse=True)
        return ordered[:limit] if limit is not None else ordered


def _capacity_env(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)
