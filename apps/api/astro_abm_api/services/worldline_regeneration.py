from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from astro_abm_api.models.report import (
    ScenarioReport,
    WorldlineDay,
    WorldlineGenerationConfig,
    WorldlineSimulation,
    WorldlineState,
)
from astro_abm_api.models.scenario import ScenarioWorldlineChunkRequest
from astro_abm_api.services.worldline_llm_generator import generate_worldline_chunk
from astro_abm_api.services.worldline_simulation import (
    generate_worldline_days_for_range,
    generate_worldline_simulation,
    hash_worldline_state,
)


@dataclass(frozen=True)
class WorldlineChunk:
    chunk_index: int
    start_date: date
    end_date: date


@dataclass(frozen=True)
class RegenerationResult:
    report: ScenarioReport
    rebuilt_chunk_count: int


def regenerate_worldline_from_chunk(
    report: ScenarioReport,
    *,
    start_chunk_index: int,
    note: str | None = None,
) -> RegenerationResult:
    if not report.daily_timeline:
        raise ValueError("daily_timeline is required for worldline regeneration")
    if report.worldline_simulation is None:
        raise ValueError("worldline_simulation is required for worldline regeneration")

    generation_config, preset_note = _resolve_generation_config(report)
    chunks = _build_chunks(
        [snapshot.date for snapshot in report.daily_timeline],
        generation_config.worldline_chunk_days,
    )
    if start_chunk_index < 0 or start_chunk_index >= len(chunks):
        raise ValueError("start_chunk_index is out of range")

    working_report = report
    chunk_history = _chunk_history_before(
        report.worldline_simulation.provenance.get("chunk_history"),
        start_chunk_index,
    )
    rebuilt_count = 0
    regenerated_at = datetime.now(UTC).isoformat()

    for chunk in chunks[start_chunk_index:]:
        previous_state = _previous_state_for_chunk(working_report, chunk)
        upstream_state_hash = hash_worldline_state(previous_state)
        if _should_use_llm(generation_config):
            chunk_days, status, output_validation, safety_check, network_call, issues = (
                _regenerate_llm_chunk(
                    working_report,
                    chunk,
                    chunks,
                    previous_state,
                    generation_config,
                )
            )
        else:
            status = (
                "fallback"
                if generation_config.worldline_provider == "llm"
                else "mock_completed"
            )
            output_validation = (
                "llm_disabled_or_config_unavailable"
                if generation_config.worldline_provider == "llm"
                else "not_run"
            )
            safety_check = "not_run"
            network_call = False
            issues = _deterministic_issues(generation_config, preset_note)
            chunk_days = _regenerate_deterministic_chunk(
                working_report,
                chunk,
                previous_state,
                chunk_status=status,
                quality_notes=issues,
            )

        output_state_hash = hash_worldline_state(chunk_days[-1].world_state_after)
        chunk_history.append(
            _chunk_history_entry(
                chunk=chunk,
                total_chunks=len(chunks),
                generation_config=generation_config,
                status=status,
                output_validation=output_validation,
                safety_check=safety_check,
                network_call=network_call,
                regenerated_at=regenerated_at,
                upstream_state_hash=upstream_state_hash,
                output_state_hash=output_state_hash,
                issues=issues,
            )
        )
        working_report = _replace_worldline_days(
            working_report,
            chunk_days,
            generation_config=generation_config,
            chunk_history=chunk_history,
            regenerated_at=regenerated_at,
            start_chunk_index=start_chunk_index,
            rebuilt_chunk_count=rebuilt_count + 1,
            note=note,
            preset_note=preset_note,
        )
        rebuilt_count += 1

    return RegenerationResult(report=working_report, rebuilt_chunk_count=rebuilt_count)


def _resolve_generation_config(
    report: ScenarioReport,
) -> tuple[WorldlineGenerationConfig, str | None]:
    existing = report.worldline_simulation
    if existing and existing.generation_config is not None:
        return existing.generation_config, None

    provenance = existing.provenance if existing else {}
    provider = str(provenance.get("provider") or "mock")
    model = provenance.get("model")
    chunk_days = _coerce_chunk_days(provenance.get("chunk_size_days"))
    generation_mode = str(provenance.get("generation_mode") or "")
    worldline_provider = "llm" if "llm" in generation_mode else "deterministic_mock"
    note = "Original generation preset was unavailable; fallback settings were used."
    return (
        WorldlineGenerationConfig(
            worldline_provider=worldline_provider,
            worldline_chunk_days=chunk_days,
            llm_provider=provider if provider in {"mock", "openai_compatible"} else "mock",
            llm_model=str(model) if isinstance(model, str) and model else None,
            report_language=report.language,
            credential_status=str(provenance.get("credential_status") or "unavailable"),
        ),
        note,
    )


def _build_chunks(dates: list[date], chunk_days: int) -> list[WorldlineChunk]:
    chunks: list[WorldlineChunk] = []
    for offset in range(0, len(dates), chunk_days):
        chunk_dates = dates[offset : offset + chunk_days]
        chunks.append(
            WorldlineChunk(
                chunk_index=len(chunks) + 1,
                start_date=chunk_dates[0],
                end_date=chunk_dates[-1],
            )
        )
    return chunks


def _previous_state_for_chunk(
    report: ScenarioReport,
    chunk: WorldlineChunk,
) -> WorldlineState:
    worldline = report.worldline_simulation
    if worldline is None:
        fallback = generate_worldline_simulation(report)
        if fallback is None:
            raise ValueError("worldline_simulation is required for regeneration")
        return fallback.days[0].world_state_before
    previous_days = [day for day in worldline.days if day.date < chunk.start_date]
    if previous_days:
        return sorted(previous_days, key=lambda day: day.date)[-1].world_state_after
    first_day = sorted(worldline.days, key=lambda day: day.date)[0]
    return first_day.world_state_before


def _should_use_llm(config: WorldlineGenerationConfig) -> bool:
    return (
        config.worldline_provider == "llm"
        and config.llm_provider == "openai_compatible"
        and config.llm_real_enabled is True
        and bool(config.llm_base_url)
        and bool(config.llm_model)
    )


def _regenerate_llm_chunk(
    report: ScenarioReport,
    chunk: WorldlineChunk,
    chunks: list[WorldlineChunk],
    previous_state: WorldlineState,
    generation_config: WorldlineGenerationConfig,
) -> tuple[list[WorldlineDay], str, str, str, bool, list[str]]:
    request = ScenarioWorldlineChunkRequest(
        llm_provider="openai_compatible",
        llm_real_enabled=generation_config.llm_real_enabled,
        llm_base_url=generation_config.llm_base_url,
        llm_model=generation_config.llm_model,
        llm_api_key=None,
        llm_user_prompt=generation_config.custom_user_prompt,
        llm_timeout_seconds=generation_config.llm_timeout_seconds,
        llm_max_output_tokens=generation_config.llm_max_output_tokens,
        llm_call_delay_seconds=generation_config.llm_call_delay_seconds,
        language=generation_config.report_language or report.language or "en",
        chunk_start_date=chunk.start_date,
        chunk_end_date=chunk.end_date,
        chunk_index=chunk.chunk_index,
        total_chunks=len(chunks),
        worldline_chunk_days=_coerce_chunk_days(generation_config.worldline_chunk_days),
    )
    generated = generate_worldline_chunk(request, report)
    provenance = generated.provenance
    chunk_days = [
        day
        for day in generated.days
        if chunk.start_date <= day.date <= chunk.end_date
    ]
    if not chunk_days or generated.status != "completed":
        issues = [
            "LLM regeneration failed safely; deterministic fallback chunk was used.",
            str(provenance.get("last_error") or provenance.get("output_validation_status") or ""),
        ]
        chunk_days = _regenerate_deterministic_chunk(
            report,
            chunk,
            previous_state,
            chunk_status="fallback",
            quality_notes=issues,
        )
        return (
            chunk_days,
            "fallback",
            str(provenance.get("output_validation_status") or "fallback"),
            str(provenance.get("safety_check_status") or "not_run"),
            bool(provenance.get("network_call_performed")),
            issues,
        )
    return (
        chunk_days,
        str(provenance.get("chunk_status") or generated.status),
        str(provenance.get("output_validation_status") or "valid_json"),
        str(provenance.get("safety_check_status") or "passed"),
        bool(provenance.get("network_call_performed")),
        _string_list(provenance.get("llm_output_quality_notes")),
    )


def _regenerate_deterministic_chunk(
    report: ScenarioReport,
    chunk: WorldlineChunk,
    previous_state: WorldlineState,
    *,
    chunk_status: str,
    quality_notes: list[str],
) -> list[WorldlineDay]:
    return generate_worldline_days_for_range(
        report,
        start_date=chunk.start_date,
        end_date=chunk.end_date,
        previous_state=previous_state,
        generation_source="fallback" if chunk_status == "fallback" else "deterministic_mock",
        chunk_index=chunk.chunk_index,
        chunk_status=chunk_status,
        quality_notes=quality_notes,
    )


def _replace_worldline_days(
    report: ScenarioReport,
    chunk_days: list[WorldlineDay],
    *,
    generation_config: WorldlineGenerationConfig,
    chunk_history: list[dict[str, object]],
    regenerated_at: str,
    start_chunk_index: int,
    rebuilt_chunk_count: int,
    note: str | None,
    preset_note: str | None,
) -> ScenarioReport:
    existing = report.worldline_simulation
    if existing is None:
        raise ValueError("worldline_simulation is required for regeneration")
    by_date = {day.date: day for day in existing.days}
    by_date.update({day.date: day for day in chunk_days})
    merged_days = [by_date[key] for key in sorted(by_date)]
    provenance = _updated_provenance(existing, generation_config, chunk_history)
    caveats = _merge_strings(
        existing.caveats,
        [preset_note] if preset_note else [],
        ["Regeneration rebuilt the selected chunk and all downstream chunks sequentially."],
    )
    updated_worldline = WorldlineSimulation(
        status=existing.status if existing.status != "mock_completed" else "mock_completed",
        mode=existing.mode,
        horizon_days=len(merged_days),
        days=merged_days,
        summary=existing.summary,
        caveats=caveats,
        provenance=provenance,
        generation_config=generation_config,
        continuity_status="consistent",
        last_regeneration={
            "regenerated_at": regenerated_at,
            "start_chunk_index": start_chunk_index,
            "rebuilt_chunk_count": rebuilt_chunk_count,
            "note": note,
            "preset_note": preset_note,
        },
    )
    return report.model_copy(update={"worldline_simulation": updated_worldline})


def _updated_provenance(
    existing: WorldlineSimulation,
    generation_config: WorldlineGenerationConfig,
    chunk_history: list[dict[str, object]],
) -> dict[str, object]:
    failed_count = sum(1 for item in chunk_history if item.get("status") == "fallback")
    return {
        **existing.provenance,
        "generation_mode": (
            "llm_chunk_v1"
            if generation_config.worldline_provider == "llm"
            else "deterministic_mock_v1"
        ),
        "provider": generation_config.llm_provider,
        "model": generation_config.llm_model,
        "chunk_size_days": generation_config.worldline_chunk_days,
        "network_call_performed": any(
            bool(item.get("network_call_performed")) for item in chunk_history
        ),
        "credential_status": generation_config.credential_status,
        "chunk_count": len(chunk_history),
        "failed_chunk_count": failed_count,
        "chunk_history": chunk_history,
    }


def _chunk_history_before(value: object, start_chunk_index: int) -> list[dict[str, object]]:
    history = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    return [
        dict(item)
        for item in history
        if _int_or_none(item.get("chunk_index")) is not None
        and int(item["chunk_index"]) <= start_chunk_index
    ]


def _chunk_history_entry(
    *,
    chunk: WorldlineChunk,
    total_chunks: int,
    generation_config: WorldlineGenerationConfig,
    status: str,
    output_validation: str,
    safety_check: str,
    network_call: bool,
    regenerated_at: str,
    upstream_state_hash: str,
    output_state_hash: str,
    issues: list[str],
) -> dict[str, object]:
    return {
        "chunk_index": chunk.chunk_index,
        "total_chunks": total_chunks,
        "chunk_start_date": chunk.start_date.isoformat(),
        "chunk_end_date": chunk.end_date.isoformat(),
        "generation_mode": (
            "llm_chunk_v1"
            if generation_config.worldline_provider == "llm"
            else "deterministic_mock_v1"
        ),
        "provider": generation_config.llm_provider,
        "model": generation_config.llm_model,
        "status": status,
        "quality_status": "fallback" if status == "fallback" else "completed",
        "quality_score": 0.4 if status == "fallback" else 0.8,
        "output_validation_status": output_validation,
        "safety_check_status": safety_check,
        "network_call_performed": network_call,
        "issues": issues,
        "notes": issues,
        "regenerated_at": regenerated_at,
        "depends_on_previous_chunk": chunk.chunk_index > 1,
        "upstream_state_hash": upstream_state_hash,
        "output_state_hash": output_state_hash,
    }


def _deterministic_issues(
    config: WorldlineGenerationConfig,
    preset_note: str | None,
) -> list[str]:
    issues = [
        "Regenerated with deterministic path-dependent fallback.",
        "No API key or secret was saved or reused from the scenario file.",
    ]
    if config.worldline_provider == "llm":
        issues.append(
            "Original worldline mode was LLM, but real LLM settings or credentials were unavailable at regeneration time."
        )
    if preset_note:
        issues.append(preset_note)
    return issues


def _coerce_chunk_days(value: object) -> Literal[1, 2, 3, 5]:
    try:
        numeric = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 3
    return numeric if numeric in {1, 2, 3, 5} else 3  # type: ignore[return-value]


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _merge_strings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item and item not in seen:
                merged.append(item)
                seen.add(item)
    return merged
