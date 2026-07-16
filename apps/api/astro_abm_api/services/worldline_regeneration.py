from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import sleep
from typing import Literal

from astro_abm_api.models.report import (
    LlmRegenerationOverrides,
    ScenarioReport,
    WorldlineDay,
    WorldlineGenerationConfig,
    WorldlineSimulation,
    WorldlineState,
)
from astro_abm_api.models.scenario import ScenarioWorldlineChunkRequest
from astro_abm_api.services.worldline_llm_generator import generate_worldline_chunk
from astro_abm_api.services.llm_preset_store import LlmPresetNotFoundError, LlmPresetStore
from astro_abm_api.services.worldline_simulation import (
    ensure_worldline_state_continuity,
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
    regeneration_status: str
    llm_completed_chunk_count: int
    fallback_chunk_count: int
    skipped_chunk_count: int


def regenerate_worldline_from_chunk(
    report: ScenarioReport,
    *,
    start_chunk_index: int,
    note: str | None = None,
    regeneration_id: str | None = None,
    progressive: bool = False,
    preset_id: str | None = None,
    llm_overrides: LlmRegenerationOverrides | None = None,
) -> RegenerationResult:
    if not report.daily_timeline:
        raise ValueError("daily_timeline is required for worldline regeneration")
    if report.worldline_simulation is None:
        raise ValueError("worldline_simulation is required for worldline regeneration")

    regeneration_id = _resolve_regeneration_id(
        report,
        requested_id=regeneration_id,
        start_chunk_index=start_chunk_index,
        progressive=progressive,
    )
    generation_config, preset_note, api_key = _resolve_generation_config(
        report,
        preset_id=preset_id,
        overrides=llm_overrides,
    )
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
    previous_regeneration = report.worldline_simulation.last_regeneration or {}
    same_progressive_run = bool(
        regeneration_id
        and previous_regeneration.get("regeneration_id") == regeneration_id
    )
    rebuilt_before = (
        int(previous_regeneration.get("rebuilt_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    rebuilt_count = 0
    llm_completed_count = (
        int(previous_regeneration.get("llm_completed_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    fallback_count = (
        int(previous_regeneration.get("fallback_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    skipped_count = (
        int(previous_regeneration.get("skipped_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    configuration_fallback_count = (
        int(previous_regeneration.get("configuration_fallback_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    llm_failed_count = (
        int(previous_regeneration.get("llm_failed_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    consecutive_failed_count = (
        int(previous_regeneration.get("consecutive_failed_chunk_count") or 0)
        if same_progressive_run
        else 0
    )
    generation_halted = bool(
        previous_regeneration.get("generation_halted", False)
        if same_progressive_run
        else False
    )
    first_failure = (
        str(previous_regeneration.get("error_summary") or "") or None
        if same_progressive_run
        else None
    )
    regenerated_at = (
        str(previous_regeneration.get("regenerated_at"))
        if same_progressive_run
        else datetime.now(UTC).isoformat()
    )

    rebuild_chunks = chunks[start_chunk_index : start_chunk_index + 1] if progressive else chunks[start_chunk_index:]
    for rebuild_offset, chunk in enumerate(rebuild_chunks):
        previous_state = _previous_state_for_chunk(working_report, chunk)
        upstream_state_hash = hash_worldline_state(previous_state)
        if generation_halted:
            status = "skipped_after_halt"
            output_validation = "skipped_after_consecutive_failures"
            safety_check = "not_run"
            network_call = False
            issues = [
                "LLM call skipped after an earlier chunk exhausted its retry policy; user retry is required.",
            ]
            chunk_days = _regenerate_deterministic_chunk(
                working_report,
                chunk,
                previous_state,
                chunk_status="fallback",
                quality_notes=issues,
            )
            skipped_count += 1
            generation_details: dict[str, object] = {
                "attempt_count": 0,
                "max_attempts": 3,
                "attempt_history": [],
                "safety_violation_codes": [],
            }
        elif _should_use_llm(generation_config):
            (
                chunk_days,
                status,
                output_validation,
                safety_check,
                network_call,
                issues,
                generation_details,
            ) = (
                _regenerate_llm_chunk(
                    working_report,
                    chunk,
                    chunks,
                    previous_state,
                    generation_config,
                    api_key,
                )
            )
            if status == "completed":
                llm_completed_count += 1
                consecutive_failed_count = 0
            else:
                fallback_count += 1
                llm_failed_count += 1
                consecutive_failed_count += 1
                if first_failure is None:
                    first_failure = next((item for item in issues[1:] if item), issues[0])
                if consecutive_failed_count >= 1:
                    generation_halted = True
        else:
            configuration_fallback = _llm_configuration_fallback(generation_config)
            status = (
                "fallback"
                if generation_config.worldline_provider == "llm"
                else "mock_completed"
            )
            output_validation = (
                configuration_fallback[0]
                if configuration_fallback is not None
                else "not_run"
            )
            safety_check = "not_run"
            network_call = False
            issues = _deterministic_issues(
                generation_config,
                preset_note,
                fallback_reason=(
                    configuration_fallback[0]
                    if configuration_fallback is not None
                    else None
                ),
            )
            chunk_days = _regenerate_deterministic_chunk(
                working_report,
                chunk,
                previous_state,
                chunk_status=status,
                quality_notes=issues,
            )
            generation_details = {
                "attempt_count": 0,
                "attempt_history": [],
                "safety_violation_codes": [],
            }
            if configuration_fallback is not None:
                fallback_reason, recommended_action, _ = configuration_fallback
                generation_details.update(
                    {
                        "fallback_reason": fallback_reason,
                        "request_diagnostics": {
                            "error_category": "configuration",
                            "failure_kind": fallback_reason,
                            "recommended_action": recommended_action,
                            "exception_type": None,
                            "retryable": False,
                            "http_status": None,
                        },
                    }
                )
            if generation_config.worldline_provider == "llm":
                fallback_count += 1
                configuration_fallback_count += 1
                if first_failure is None:
                    first_failure = next((item for item in issues if item), None)

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
                generation_details=generation_details,
            )
        )
        working_report = _replace_worldline_days(
            working_report,
            chunk_days,
            generation_config=generation_config,
            chunk_history=chunk_history,
            regenerated_at=regenerated_at,
            start_chunk_index=start_chunk_index,
            rebuilt_chunk_count=rebuilt_before + rebuilt_count + 1,
            note=note,
            preset_note=preset_note,
            regeneration_id=regeneration_id,
            regeneration_complete=chunk.chunk_index == len(chunks),
            pending_chunk_count=len(chunks) - chunk.chunk_index,
            next_chunk_index=(
                chunk.chunk_index if chunk.chunk_index < len(chunks) else None
            ),
            next_chunk_date=(
                chunks[chunk.chunk_index].start_date
                if chunk.chunk_index < len(chunks)
                else None
            ),
        )
        rebuilt_count += 1
        delay_seconds = generation_config.llm_call_delay_seconds or 0
        if network_call and delay_seconds > 0 and rebuild_offset < len(rebuild_chunks) - 1:
            sleep(delay_seconds)

    regeneration_status = _regeneration_status(
        llm_completed_count=llm_completed_count,
        fallback_count=fallback_count,
        skipped_count=skipped_count,
        configuration_fallback_count=configuration_fallback_count,
        worldline_provider=generation_config.worldline_provider,
    )
    working_report = _finalize_regeneration(
        working_report,
        regeneration_status=regeneration_status,
        llm_completed_count=llm_completed_count,
        fallback_count=fallback_count,
        skipped_count=skipped_count,
        configuration_fallback_count=configuration_fallback_count,
        llm_failed_count=llm_failed_count,
        generation_halted=generation_halted,
        consecutive_failed_count=consecutive_failed_count,
        first_failure=first_failure,
    )
    return RegenerationResult(
        report=working_report,
        rebuilt_chunk_count=rebuilt_before + rebuilt_count,
        regeneration_status=regeneration_status,
        llm_completed_chunk_count=llm_completed_count,
        fallback_chunk_count=fallback_count,
        skipped_chunk_count=skipped_count,
    )


def _resolve_regeneration_id(
    report: ScenarioReport,
    *,
    requested_id: str | None,
    start_chunk_index: int,
    progressive: bool,
) -> str | None:
    if requested_id or not progressive:
        return requested_id
    simulation = report.worldline_simulation
    last_regeneration = simulation.last_regeneration if simulation else None
    if (
        simulation is None
        or simulation.continuity_status != "rebuilding"
        or not isinstance(last_regeneration, dict)
        or _int_or_none(last_regeneration.get("next_chunk_index")) != start_chunk_index
    ):
        return requested_id
    saved_id = last_regeneration.get("regeneration_id")
    return saved_id if isinstance(saved_id, str) and saved_id else requested_id


def _resolve_generation_config(
    report: ScenarioReport,
    *,
    preset_id: str | None = None,
    overrides: LlmRegenerationOverrides | None = None,
) -> tuple[WorldlineGenerationConfig, str | None, str | None]:
    existing = report.worldline_simulation
    if existing and existing.generation_config is not None:
        config = existing.generation_config
        preset_note = None
    else:
        provenance = existing.provenance if existing else {}
        provider = str(provenance.get("provider") or "mock")
        model = provenance.get("model")
        chunk_days = _coerce_chunk_days(provenance.get("chunk_size_days"))
        generation_mode = str(provenance.get("generation_mode") or "")
        worldline_provider = "llm" if "llm" in generation_mode else "deterministic_mock"
        preset_note = "Original generation preset was unavailable; fallback settings were used."
        config = WorldlineGenerationConfig(
            worldline_provider=worldline_provider,
            worldline_chunk_days=chunk_days,
            llm_provider=provider if provider in {"mock", "openai_compatible"} else "mock",
            llm_model=str(model) if isinstance(model, str) and model else None,
            report_language=report.language,
            credential_status=str(provenance.get("credential_status") or "unavailable"),
        )

    api_key: str | None = None
    effective_preset_id = preset_id or config.preset_id
    record: dict[str, object] | None = None
    if effective_preset_id:
        try:
            record = LlmPresetStore().get_record(effective_preset_id)
        except (LlmPresetNotFoundError, ValueError):
            if preset_id:
                raise
            preset_note = (
                "Original local LLM preset was unavailable; environment or fallback "
                "credentials were used."
            )
            config = config.model_copy(update={"credential_status": "unavailable"})
    if record is not None and effective_preset_id:
        api_key = record.get("api_key")
        config = config.model_copy(
            update={
                "worldline_provider": "llm",
                "llm_provider": record.get("provider", "openai_compatible"),
                "llm_real_enabled": bool(record.get("real_enabled", True)),
                "llm_base_url": record.get("base_url"),
                "llm_model": record.get("model"),
                "llm_timeout_seconds": record.get("timeout_seconds"),
                "llm_max_output_tokens": record.get("max_output_tokens"),
                "llm_call_delay_seconds": record.get("call_delay_seconds"),
                "custom_user_prompt": record.get("custom_user_prompt"),
                "report_language": report.language,
                "preset_id": effective_preset_id,
                "preset_name": record.get("name"),
                "credential_status": "stored_local" if api_key else "env_required",
            }
        )
        preset_note = f"Local LLM preset reused: {record.get('name') or effective_preset_id}."

    if overrides is not None:
        updates: dict[str, object] = {}
        mapping = {
            "real_enabled": "llm_real_enabled",
            "base_url": "llm_base_url",
            "model": "llm_model",
            "timeout_seconds": "llm_timeout_seconds",
            "max_output_tokens": "llm_max_output_tokens",
            "call_delay_seconds": "llm_call_delay_seconds",
            "custom_user_prompt": "custom_user_prompt",
        }
        for source, target in mapping.items():
            value = getattr(overrides, source)
            if value is not None:
                updates[target] = value
        if overrides.api_key:
            api_key = overrides.api_key
            updates["credential_status"] = "request_transient"
        if updates:
            config = config.model_copy(update=updates)

    return config, preset_note, api_key


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


def _llm_configuration_fallback(
    config: WorldlineGenerationConfig,
) -> tuple[str, str, str] | None:
    if config.worldline_provider != "llm":
        return None
    if config.llm_provider != "openai_compatible":
        return (
            "unsupported_llm_provider",
            "select_openai_compatible",
            "OpenAI-compatible LLM mode was not configured; deterministic fallback was used without a network call.",
        )
    if config.llm_real_enabled is not True:
        return (
            "real_llm_disabled",
            "enable_real_llm",
            "Real LLM calls were disabled; deterministic fallback was used without a network call.",
        )
    if not config.llm_base_url:
        return (
            "llm_base_url_missing",
            "configure_endpoint",
            "The LLM base URL was missing; deterministic fallback was used without a network call.",
        )
    if not config.llm_model:
        return (
            "llm_model_missing",
            "configure_model",
            "The LLM model was missing; deterministic fallback was used without a network call.",
        )
    return None


def _regenerate_llm_chunk(
    report: ScenarioReport,
    chunk: WorldlineChunk,
    chunks: list[WorldlineChunk],
    previous_state: WorldlineState,
    generation_config: WorldlineGenerationConfig,
    api_key: str | None,
) -> tuple[
    list[WorldlineDay],
    str,
    str,
    str,
    bool,
    list[str],
    dict[str, object],
]:
    request = ScenarioWorldlineChunkRequest(
        llm_provider="openai_compatible",
        llm_real_enabled=generation_config.llm_real_enabled,
        llm_base_url=generation_config.llm_base_url,
        llm_model=generation_config.llm_model,
        llm_api_key=api_key,
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
    generation_details = _safe_generation_details(provenance)
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
            generation_details,
        )
    return (
        chunk_days,
        str(provenance.get("chunk_status") or generated.status),
        str(provenance.get("output_validation_status") or "valid_json"),
        str(provenance.get("safety_check_status") or "passed"),
        bool(provenance.get("network_call_performed")),
        _string_list(provenance.get("llm_output_quality_notes")),
        generation_details,
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
    regeneration_id: str | None,
    regeneration_complete: bool,
    pending_chunk_count: int,
    next_chunk_index: int | None,
    next_chunk_date: date | None,
) -> ScenarioReport:
    existing = report.worldline_simulation
    if existing is None:
        raise ValueError("worldline_simulation is required for regeneration")
    by_date = {day.date: day for day in existing.days}
    by_date.update({day.date: day for day in chunk_days})
    ordered_days = [by_date[key] for key in sorted(by_date)]
    merged_days = (
        ensure_worldline_state_continuity(ordered_days)
        if regeneration_complete
        else ordered_days
    )
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
        continuity_status="consistent" if regeneration_complete else "rebuilding",
        last_regeneration={
            "regeneration_id": regeneration_id,
            "regenerated_at": regenerated_at,
            "start_chunk_index": start_chunk_index,
            "rebuilt_chunk_count": rebuilt_chunk_count,
            "note": note,
            "preset_note": preset_note,
            "pending_chunk_count": pending_chunk_count,
            "next_chunk_index": next_chunk_index,
            "next_chunk_date": next_chunk_date.isoformat() if next_chunk_date else None,
        },
    )
    return report.model_copy(update={"worldline_simulation": updated_worldline})


def _updated_provenance(
    existing: WorldlineSimulation,
    generation_config: WorldlineGenerationConfig,
    chunk_history: list[dict[str, object]],
) -> dict[str, object]:
    failed_count = sum(
        1
        for item in chunk_history
        if item.get("status") == "fallback"
    )
    skipped_count = sum(
        1 for item in chunk_history if item.get("status") == "skipped_after_halt"
    )
    fallback_reason_counts = _fallback_reason_counts(chunk_history)
    configuration_fallback_count = sum(
        fallback_reason_counts.get(reason, 0)
        for reason in _CONFIGURATION_FALLBACK_REASONS
    )
    llm_failed_count = sum(
        1
        for item in chunk_history
        if item.get("status") == "fallback"
        and item.get("fallback_reason") not in _CONFIGURATION_FALLBACK_REASONS
    )
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
        "skipped_chunk_count": skipped_count,
        "configuration_fallback_chunk_count": configuration_fallback_count,
        "llm_failed_chunk_count": llm_failed_count,
        "fallback_reason_counts": fallback_reason_counts,
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
    generation_details: dict[str, object],
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
        "quality_status": (
            "fallback" if status in {"fallback", "skipped_after_halt"} else "completed"
        ),
        "quality_score": 0.4 if status in {"fallback", "skipped_after_halt"} else 0.8,
        "output_validation_status": output_validation,
        "safety_check_status": safety_check,
        "network_call_performed": network_call,
        "issues": issues,
        "notes": issues,
        "regenerated_at": regenerated_at,
        "depends_on_previous_chunk": chunk.chunk_index > 1,
        "upstream_state_hash": upstream_state_hash,
        "output_state_hash": output_state_hash,
        **generation_details,
    }


def _safe_generation_details(provenance: dict[str, object]) -> dict[str, object]:
    keys = (
        "attempt_count",
        "max_attempts",
        "last_error",
        "response_diagnostics",
        "request_diagnostics",
        "attempt_history",
        "safety_violation_codes",
        "consecutive_failed_chunk_count",
        "generation_halted",
    )
    return {key: provenance[key] for key in keys if key in provenance}


def _regeneration_status(
    *,
    llm_completed_count: int,
    fallback_count: int,
    skipped_count: int,
    configuration_fallback_count: int,
    worldline_provider: str,
) -> str:
    if worldline_provider != "llm":
        return "completed"
    if fallback_count == 0 and skipped_count == 0:
        return "completed"
    if fallback_count > 0 and fallback_count == configuration_fallback_count and skipped_count == 0:
        return "configuration_fallback"
    if llm_completed_count > 0:
        return "partial_fallback"
    return "failed_fallback"


def _finalize_regeneration(
    report: ScenarioReport,
    *,
    regeneration_status: str,
    llm_completed_count: int,
    fallback_count: int,
    skipped_count: int,
    configuration_fallback_count: int,
    llm_failed_count: int,
    generation_halted: bool,
    consecutive_failed_count: int,
    first_failure: str | None,
) -> ScenarioReport:
    worldline = report.worldline_simulation
    if worldline is None:
        return report
    effective_status = (
        "in_progress"
        if worldline.continuity_status == "rebuilding"
        else regeneration_status
    )
    last_regeneration = {
        **(worldline.last_regeneration or {}),
        "status": effective_status,
        "llm_completed_chunk_count": llm_completed_count,
        "fallback_chunk_count": fallback_count,
        "skipped_chunk_count": skipped_count,
        "configuration_fallback_chunk_count": configuration_fallback_count,
        "llm_failed_chunk_count": llm_failed_count,
        "generation_halted": generation_halted,
        "consecutive_failed_chunk_count": consecutive_failed_count,
        "error_summary": first_failure,
    }
    provenance = {
        **worldline.provenance,
        "last_regeneration_status": effective_status,
        "last_regeneration_llm_completed_chunk_count": llm_completed_count,
        "last_regeneration_fallback_chunk_count": fallback_count,
        "last_regeneration_skipped_chunk_count": skipped_count,
        "last_regeneration_configuration_fallback_chunk_count": configuration_fallback_count,
        "last_regeneration_llm_failed_chunk_count": llm_failed_count,
        "generation_halted": generation_halted,
        "halt_reason": (
            "One LLM chunk exhausted its retry policy during regeneration; remaining network calls were skipped until user retry."
            if generation_halted
            else None
        ),
    }
    status = {
        "completed": "completed",
        "partial_fallback": "completed_with_fallback",
        "failed_fallback": "fallback",
        "configuration_fallback": "completed_with_fallback",
    }[regeneration_status]
    return report.model_copy(
        update={
            "worldline_simulation": worldline.model_copy(
                update={
                    "status": status,
                    "last_regeneration": last_regeneration,
                    "provenance": provenance,
                }
            )
        }
    )


def _deterministic_issues(
    config: WorldlineGenerationConfig,
    preset_note: str | None,
    *,
    fallback_reason: str | None = None,
) -> list[str]:
    configuration_fallback = _llm_configuration_fallback(config)
    reason_message = (
        configuration_fallback[2]
        if configuration_fallback is not None and configuration_fallback[0] == fallback_reason
        else "Regenerated with deterministic path-dependent fallback."
    )
    issues = [reason_message, "No API key or secret was saved or reused from the scenario file."]
    if preset_note:
        issues.append(preset_note)
    return issues


_CONFIGURATION_FALLBACK_REASONS = {
    "unsupported_llm_provider",
    "real_llm_disabled",
    "llm_base_url_missing",
    "llm_model_missing",
    "legacy_configuration_unavailable",
}


def _fallback_reason_counts(
    chunk_history: list[dict[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in chunk_history:
        reason = item.get("fallback_reason")
        if (
            not reason
            and item.get("status") == "fallback"
            and not item.get("network_call_performed")
            and item.get("output_validation_status")
            in {
                "configuration_missing",
                "llm_disabled_or_config_unavailable",
                "not_run",
            }
        ):
            reason = "legacy_configuration_unavailable"
        if isinstance(reason, str) and reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


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
