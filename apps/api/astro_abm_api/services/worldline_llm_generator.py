from __future__ import annotations

import json
from datetime import date
from typing import Any

import requests

from astro_abm_api.models.report import (
    ScenarioReport,
    WorldlineAgentEvent,
    WorldlineCausalLink,
    WorldlineDay,
    WorldlineGenerationConfig,
    WorldlineImpactScores,
    WorldlineSimulation,
    WorldlineState,
)
from astro_abm_api.models.scenario import ScenarioCreateRequest, ScenarioWorldlineChunkRequest
from astro_abm_api.services.llm_client import (
    _call_openai_compatible,
    build_llm_config,
    credential_status,
    diagnose_llm_json,
    parse_llm_json,
    safety_check_text,
)
from astro_abm_api.services.worldline_llm_context import build_worldline_llm_context
from astro_abm_api.services.worldline_llm_prompts import (
    WORLDLINE_PROMPT_TEMPLATE_VERSION,
    build_worldline_messages,
    build_worldline_retry_messages,
)
from astro_abm_api.services.worldline_simulation import (
    WORLDLINE_DISCLAIMER,
    ensure_worldline_state_continuity,
    generate_worldline_simulation,
)

MAX_WORLDLINE_CHUNK_ATTEMPTS = 3
MAX_CONSECUTIVE_FAILED_CHUNKS = 2


def generate_worldline_for_request(
    request: ScenarioCreateRequest,
    report: ScenarioReport,
) -> WorldlineSimulation | None:
    if request.worldline_provider == "deterministic_mock":
        return generate_worldline_simulation(report)

    config = build_llm_config(
        provider=request.llm_provider,
        base_url=request.llm_base_url,
        model=request.llm_model,
        api_key=request.llm_api_key,
        real_enabled=request.llm_real_enabled,
        timeout_seconds=request.llm_timeout_seconds,
        max_output_tokens=request.llm_max_output_tokens,
    )
    fallback = generate_worldline_simulation(report)
    if fallback is None:
        return None
    generation_config = _generation_config_from_request(
        worldline_provider="llm",
        chunk_days=request.worldline_chunk_days,
        llm_provider=request.llm_provider,
        llm_real_enabled=request.llm_real_enabled,
        llm_base_url=request.llm_base_url,
        llm_model=request.llm_model,
        llm_timeout_seconds=request.llm_timeout_seconds,
        llm_max_output_tokens=request.llm_max_output_tokens,
        llm_call_delay_seconds=request.llm_call_delay_seconds,
        report_language=request.language,
        custom_user_prompt=request.llm_user_prompt,
        credential_status_value=credential_status(config),
    )
    if not config.real_calls_enabled:
        return _with_provenance(
            fallback,
            status="dry_run",
            mode="llm_chunk_v1",
            provider=config.provider,
            model=config.model,
            credential_status_value=credential_status(config),
            chunk_size_days=request.worldline_chunk_days,
            network_call_performed=False,
            input_context_hash="",
            output_validation_status="not_run",
            safety_check_status="not_run",
            chunk_count=0,
            failed_chunk_count=0,
            caveat="Real LLM worldline calls are disabled; deterministic fallback worldline was used.",
            generation_config=generation_config,
        )
    return _with_provenance(
        fallback,
        status="fallback",
        mode="llm_chunk_v1",
        provider=config.provider,
        model=config.model,
        credential_status_value=credential_status(config),
        chunk_size_days=request.worldline_chunk_days,
        network_call_performed=False,
        input_context_hash="",
        output_validation_status="deferred_to_chunk_endpoint",
        safety_check_status="not_run",
        chunk_count=0,
        failed_chunk_count=0,
        caveat="LLM worldline mode selected; call the chunk endpoint to replace deterministic fallback days.",
        generation_config=generation_config,
    )


def generate_worldline_chunk(
    request: ScenarioWorldlineChunkRequest,
    report: ScenarioReport,
) -> WorldlineSimulation:
    config = build_llm_config(
        provider=request.llm_provider,
        base_url=request.llm_base_url,
        model=request.llm_model,
        api_key=request.llm_api_key,
        real_enabled=request.llm_real_enabled,
        timeout_seconds=request.llm_timeout_seconds,
        max_output_tokens=request.llm_max_output_tokens,
    )
    fallback = generate_worldline_simulation(report)
    generation_config = _generation_config_from_request(
        worldline_provider="llm",
        chunk_days=request.worldline_chunk_days,
        llm_provider=request.llm_provider,
        llm_real_enabled=request.llm_real_enabled,
        llm_base_url=request.llm_base_url,
        llm_model=request.llm_model,
        llm_timeout_seconds=request.llm_timeout_seconds,
        llm_max_output_tokens=request.llm_max_output_tokens,
        llm_call_delay_seconds=request.llm_call_delay_seconds,
        report_language=request.language,
        custom_user_prompt=request.llm_user_prompt,
        credential_status_value=credential_status(config),
    )
    if fallback is None:
        return WorldlineSimulation(
            status="failed",
            mode="llm_chunk_v1",
            horizon_days=0,
            days=[],
            summary="No daily timeline is available for worldline generation.",
            caveats=["Worldline generation requires daily_timeline."],
            provenance=_provenance(
                report,
                request,
                provider=config.provider,
                model=config.model,
                credential_status_value=credential_status(config),
                network_call_performed=False,
                input_context_hash="",
                output_validation_status="missing_daily_timeline",
                safety_check_status="not_run",
                failed=True,
                attempt_count=0,
                last_error="daily_timeline is missing",
            ),
            generation_config=generation_config,
            continuity_status="consistent",
        )

    if _generation_circuit_is_open(report, request):
        return _halted_generation(report, generation_config)

    if not config.real_calls_enabled:
        return _with_provenance(
            fallback,
            status="dry_run",
            mode="llm_chunk_v1",
            provider=config.provider,
            model=config.model,
            credential_status_value=credential_status(config),
            chunk_size_days=request.worldline_chunk_days,
            network_call_performed=False,
            input_context_hash="",
            output_validation_status="not_run",
            safety_check_status="not_run",
            chunk_count=_previous_chunk_count(report),
            failed_chunk_count=_previous_failed_chunk_count(report),
            caveat="Real LLM worldline calls are disabled; deterministic fallback worldline was used.",
            generation_config=generation_config,
        )
    if not config.base_url or not config.model:
        return _fallback_chunk(
            report,
            fallback,
            request,
            provider=config.provider,
            model=config.model,
            credential_status_value=credential_status(config),
            network_call_performed=False,
            input_context_hash="",
            output_validation_status="configuration_missing",
            safety_check_status="not_run",
            reason="OpenAI-compatible worldline provider is missing base_url or model.",
            attempt_count=0,
            generation_config=generation_config,
        )

    previous_state = _previous_state_for_chunk(report, fallback, request.chunk_start_date)
    context = build_worldline_llm_context(
        report,
        chunk_start_date=request.chunk_start_date,
        chunk_end_date=request.chunk_end_date,
        previous_world_state=previous_state,
        chunk_index=request.chunk_index,
        total_chunks=request.total_chunks,
        user_prompt=request.llm_user_prompt,
    )
    context_hash = str(context["input_context_hash"])

    messages = build_worldline_messages(context)
    attempt_messages = messages
    last_failure = {
        "output_validation_status": "not_run",
        "safety_check_status": "not_run",
        "reason": "LLM worldline chunk did not complete.",
        "response_diagnostics": None,
    }
    for attempt_count in range(1, MAX_WORLDLINE_CHUNK_ATTEMPTS + 1):
        attempt = _attempt_worldline_chunk(
            config,
            attempt_messages,
            report,
            fallback,
            request,
            previous_state,
            attempt_count=attempt_count,
        )
        if attempt["ok"]:
            parsed = attempt["parsed"]
            chunk_days = attempt["chunk_days"]
            merged_days = _merge_days(report.worldline_simulation, fallback, chunk_days)
            previous_caveats = report.worldline_simulation.caveats if report.worldline_simulation else []
            return WorldlineSimulation(
                status="completed",
                mode="llm_chunk_v1",
                horizon_days=len(merged_days),
                days=merged_days,
                summary=str(parsed.get("summary") or "LLM worldline chunk generated from provided scenario context."),
                caveats=_merge_strings(
                    previous_caveats,
                    _string_list(parsed.get("caveats", [])),
                    ["LLM worldline events are simulated scenario events, not real-world causal proof."],
                ),
                provenance=_provenance(
                    report,
                    request,
                    provider=config.provider,
                    model=config.model,
                    credential_status_value=credential_status(config),
                    network_call_performed=True,
                    input_context_hash=context_hash,
                    output_validation_status="valid_json",
                    safety_check_status="passed",
                    failed=False,
                    attempt_count=attempt_count,
                    last_error=None,
                    response_diagnostics=attempt.get("response_diagnostics"),
                ),
                generation_config=generation_config,
                continuity_status="consistent",
            )
        last_failure = {
            "output_validation_status": str(attempt["output_validation_status"]),
            "safety_check_status": str(attempt["safety_check_status"]),
            "reason": str(attempt["reason"]),
            "response_diagnostics": attempt.get("response_diagnostics"),
        }
        if attempt_count < MAX_WORLDLINE_CHUNK_ATTEMPTS:
            attempt_messages = build_worldline_retry_messages(
                messages,
                language=request.language,
                output_validation_status=last_failure["output_validation_status"],
                safety_check_status=last_failure["safety_check_status"],
                next_attempt=attempt_count + 1,
            )

    return _fallback_chunk(
        report,
        fallback,
        request,
        provider=config.provider,
        model=config.model,
        credential_status_value=credential_status(config),
        network_call_performed=True,
        input_context_hash=context_hash,
        output_validation_status=last_failure["output_validation_status"],
        safety_check_status=last_failure["safety_check_status"],
        reason=last_failure["reason"],
        attempt_count=MAX_WORLDLINE_CHUNK_ATTEMPTS,
        generation_config=generation_config,
        response_diagnostics=last_failure["response_diagnostics"],
    )


def _attempt_worldline_chunk(
    config: Any,
    messages: list[dict[str, str]],
    report: ScenarioReport,
    fallback: WorldlineSimulation,
    request: ScenarioWorldlineChunkRequest,
    previous_state: WorldlineState,
    *,
    attempt_count: int,
) -> dict[str, Any]:
    try:
        raw_text = _call_openai_compatible(config, messages)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "output_validation_status": "request_failed",
            "safety_check_status": "not_run",
            "reason": f"{type(exc).__name__}: {exc}",
        }

    parsed = parse_llm_json(raw_text)
    response_diagnostics = diagnose_llm_json(raw_text)
    if parsed is None:
        return {
            "ok": False,
            "output_validation_status": "invalid_json",
            "safety_check_status": "not_run",
            "reason": "The LLM returned output that could not be parsed as strict JSON.",
            "response_diagnostics": response_diagnostics,
        }
    if not safety_check_text(json.dumps(parsed, ensure_ascii=False)):
        return {
            "ok": False,
            "output_validation_status": "valid_json",
            "safety_check_status": "failed",
            "reason": (
                "The LLM worldline chunk failed safety review and was replaced by "
                "deterministic fallback."
            ),
            "response_diagnostics": response_diagnostics,
        }

    try:
        chunk_days = _days_from_payload(
            parsed,
            report,
            fallback,
            request,
            previous_state,
            attempt_count=attempt_count,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "output_validation_status": "invalid_payload",
            "safety_check_status": "not_run",
            "reason": str(exc),
            "response_diagnostics": response_diagnostics,
        }

    return {
        "ok": True,
        "parsed": parsed,
        "chunk_days": chunk_days,
        "response_diagnostics": response_diagnostics,
    }


def _days_from_payload(
    payload: dict[str, Any],
    report: ScenarioReport,
    fallback: WorldlineSimulation,
    request: ScenarioWorldlineChunkRequest,
    previous_state: WorldlineState,
    *,
    attempt_count: int,
) -> list[WorldlineDay]:
    payload_days = payload.get("days")
    if not isinstance(payload_days, list):
        raise ValueError("worldline chunk payload must include days list")
    fallback_by_date = {day.date: day for day in fallback.days}
    raw_by_date = {
        date.fromisoformat(str(item.get("date"))): item
        for item in payload_days
        if isinstance(item, dict) and item.get("date")
    }
    agent_names = {agent.agent_id: agent.name for agent in report.agents}
    expected_dates = [
        snapshot.date
        for snapshot in report.daily_timeline
        if request.chunk_start_date <= snapshot.date <= request.chunk_end_date
    ]
    if not expected_dates:
        raise ValueError("chunk date range does not overlap daily_timeline")

    days: list[WorldlineDay] = []
    state_before = previous_state
    for current_date in expected_dates:
        fallback_day = fallback_by_date[current_date]
        raw_day = raw_by_date.get(current_date)
        if not isinstance(raw_day, dict):
            day = fallback_day.model_copy(update={"world_state_before": state_before})
            days.append(
                _mark_day(
                    day,
                    generation_source="fallback",
                    chunk_index=request.chunk_index,
                    chunk_status="missing_day_payload",
                    quality_notes=[
                        "LLM output did not include this date; deterministic fallback day was used.",
                        f"Chunk attempt {attempt_count} of {MAX_WORLDLINE_CHUNK_ATTEMPTS}.",
                    ],
                )
            )
            state_before = fallback_day.world_state_after
            continue
        agent_events = _agent_events_from_payload(raw_day.get("agent_events"), agent_names)
        if not agent_events:
            day = fallback_day.model_copy(update={"world_state_before": state_before})
            days.append(
                _mark_day(
                    day,
                    generation_source="fallback",
                    chunk_index=request.chunk_index,
                    chunk_status="missing_agent_events",
                    quality_notes=[
                        "LLM output did not include valid agent events for this date; deterministic fallback day was used.",
                        f"Chunk attempt {attempt_count} of {MAX_WORLDLINE_CHUNK_ATTEMPTS}.",
                    ],
                )
            )
            state_before = fallback_day.world_state_after
            continue
        world_state_after = _state_from_payload(raw_day.get("world_state_after"), state_before)
        day = WorldlineDay(
            date=current_date,
            day_index=fallback_day.day_index,
            generation_source="llm_chunk",
            chunk_index=request.chunk_index,
            chunk_status="completed",
            quality_notes=[
                "Generated by an LLM worldline chunk from provided scenario context.",
                "Output parsed as strict JSON and passed safety review.",
                f"Chunk completed on attempt {attempt_count} of {MAX_WORLDLINE_CHUNK_ATTEMPTS}.",
            ],
            input_context_summary=fallback_day.input_context_summary,
            world_state_before=state_before,
            agent_events=agent_events,
            causal_links=_causal_links_from_payload(raw_day.get("causal_links"), fallback_day),
            next_day_update=str(raw_day.get("next_day_update") or fallback_day.next_day_update),
            world_state_after=world_state_after,
            disclaimer=WORLDLINE_DISCLAIMER,
        )
        days.append(day)
        state_before = world_state_after
    return days


def _agent_events_from_payload(
    value: Any,
    agent_names: dict[str, str],
) -> list[WorldlineAgentEvent]:
    events: list[WorldlineAgentEvent] = []
    if not isinstance(value, list):
        return events
    for item in value:
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("agent_id") or "").strip()
        if agent_id not in agent_names:
            continue
        try:
            events.append(
                WorldlineAgentEvent(
                    agent_id=agent_id,
                    agent_name=agent_names[agent_id],
                    what_happened=str(item.get("what_happened") or ""),
                    why_it_happened=str(item.get("why_it_happened") or ""),
                    impact_on_tomorrow=str(item.get("impact_on_tomorrow") or ""),
                    impact_scores=WorldlineImpactScores.model_validate(
                        item.get("impact_scores") or {}
                    ),
                    confidence=str(item.get("confidence") or "low_llm_context_confidence"),
                    caveats=_string_list(item.get("caveats", [])),
                )
            )
        except ValueError:
            continue
    return events


def _causal_links_from_payload(
    value: Any,
    fallback_day: WorldlineDay,
) -> list[WorldlineCausalLink]:
    links: list[WorldlineCausalLink] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            links.append(
                WorldlineCausalLink(
                    source=str(item.get("source") or "scenario_context"),
                    target=str(item.get("target") or "next_day_setup"),
                    description=str(item.get("description") or ""),
                    strength=str(item.get("strength") or "low"),
                    caveats=_string_list(item.get("caveats", [])),
                )
            )
    return links or fallback_day.causal_links


def _state_from_payload(value: Any, fallback: WorldlineState) -> WorldlineState:
    if not isinstance(value, dict):
        return fallback
    return WorldlineState(
        sentiment_state=str(value.get("sentiment_state") or fallback.sentiment_state),
        narrative_pressure=_clamp_float(value.get("narrative_pressure"), fallback.narrative_pressure),
        leverage_pressure=_clamp_float(value.get("leverage_pressure"), fallback.leverage_pressure),
        liquidity_pressure=_clamp_float(value.get("liquidity_pressure"), fallback.liquidity_pressure),
        volatility_pressure=_clamp_float(value.get("volatility_pressure"), fallback.volatility_pressure),
        stress_pressure=_clamp_float(value.get("stress_pressure"), fallback.stress_pressure),
        regime_label=(
            str(value.get("regime_label"))
            if value.get("regime_label") is not None
            else fallback.regime_label
        ),
        notes=_string_list(value.get("notes", [])) or fallback.notes,
    )


def _fallback_chunk(
    report: ScenarioReport,
    fallback: WorldlineSimulation,
    request: ScenarioWorldlineChunkRequest,
    *,
    provider: str,
    model: str | None,
    credential_status_value: str,
    network_call_performed: bool,
    input_context_hash: str,
    output_validation_status: str,
    safety_check_status: str,
    reason: str,
    attempt_count: int,
    generation_config: WorldlineGenerationConfig,
    response_diagnostics: dict[str, object] | None = None,
) -> WorldlineSimulation:
    chunk_days = [
        _mark_day(
            day,
            generation_source="fallback",
            chunk_index=request.chunk_index,
            chunk_status=output_validation_status,
            quality_notes=[
                reason,
                f"LLM chunk generation attempted {attempt_count} time(s).",
                "Deterministic fallback day was used for this chunk.",
            ],
        )
        for day in fallback.days
        if request.chunk_start_date <= day.date <= request.chunk_end_date
    ]
    merged_days = _merge_days(report.worldline_simulation, fallback, chunk_days)
    return WorldlineSimulation(
        status="fallback",
        mode="llm_chunk_v1",
        horizon_days=len(merged_days),
        days=merged_days,
        summary="LLM worldline chunk failed safely; deterministic fallback days were used.",
        caveats=_merge_strings(
            report.worldline_simulation.caveats if report.worldline_simulation else [],
            fallback.caveats,
            [reason],
        ),
        provenance=_provenance(
            report,
            request,
            provider=provider,
            model=model,
            credential_status_value=credential_status_value,
            network_call_performed=network_call_performed,
            input_context_hash=input_context_hash,
            output_validation_status=output_validation_status,
            safety_check_status=safety_check_status,
            failed=True,
            attempt_count=attempt_count,
            last_error=reason,
            response_diagnostics=response_diagnostics,
        ),
        generation_config=generation_config,
        continuity_status="consistent",
    )


def _merge_days(
    existing: WorldlineSimulation | None,
    fallback: WorldlineSimulation,
    chunk_days: list[WorldlineDay],
) -> list[WorldlineDay]:
    by_date = {day.date: day for day in fallback.days}
    if existing:
        by_date.update({day.date: day for day in existing.days})
    by_date.update({day.date: day for day in chunk_days})
    return ensure_worldline_state_continuity([by_date[key] for key in sorted(by_date)])


def _previous_state_for_chunk(
    report: ScenarioReport,
    fallback: WorldlineSimulation,
    chunk_start_date: date,
) -> WorldlineState:
    source = report.worldline_simulation or fallback
    previous_days = [day for day in source.days if day.date < chunk_start_date]
    if previous_days:
        return sorted(previous_days, key=lambda day: day.date)[-1].world_state_after
    first_days = [day for day in fallback.days if day.date >= chunk_start_date]
    if first_days:
        return sorted(first_days, key=lambda day: day.date)[0].world_state_before
    return fallback.days[0].world_state_before


def _with_provenance(
    simulation: WorldlineSimulation,
    *,
    status: str,
    mode: str,
    provider: str,
    model: str | None,
    credential_status_value: str,
    chunk_size_days: int | None,
    network_call_performed: bool,
    input_context_hash: str,
    output_validation_status: str,
    safety_check_status: str,
    chunk_count: int,
    failed_chunk_count: int,
    caveat: str,
    generation_config: WorldlineGenerationConfig,
) -> WorldlineSimulation:
    return simulation.model_copy(
        update={
            "status": status,
            "mode": mode,
            "days": _mark_days_for_status(
                simulation.days,
                status=status,
                mode=mode,
                chunk_index=None,
                output_validation_status=output_validation_status,
                caveat=caveat,
            ),
            "caveats": _merge_strings(simulation.caveats, [caveat]),
            "provenance": {
                **simulation.provenance,
                "generation_mode": mode if status != "dry_run" else "dry_run",
                "provider": provider,
                "model": model,
                "prompt_template_version": WORLDLINE_PROMPT_TEMPLATE_VERSION,
                "chunk_size_days": chunk_size_days,
                "network_call_performed": network_call_performed,
                "input_context_hash": input_context_hash,
                "output_validation_status": output_validation_status,
                "safety_check_status": safety_check_status,
                "credential_status": credential_status_value,
                "chunk_count": chunk_count,
                "failed_chunk_count": failed_chunk_count,
                "llm_output_quality_notes": _merge_strings(
                    _string_list(simulation.provenance.get("llm_output_quality_notes")),
                    _quality_notes_for_status(
                        status=status,
                        output_validation_status=output_validation_status,
                        safety_check_status=safety_check_status,
                        caveat=caveat,
                    ),
                ),
                "chunk_history": _merge_chunk_history(
                    simulation.provenance.get("chunk_history"),
                    None,
                ),
            },
            "generation_config": generation_config,
            "continuity_status": "consistent",
        }
    )


def _generation_config_from_request(
    *,
    worldline_provider: str,
    chunk_days: int,
    llm_provider: str | None,
    llm_real_enabled: bool | None,
    llm_base_url: str | None,
    llm_model: str | None,
    llm_timeout_seconds: float | None,
    llm_max_output_tokens: int | None,
    llm_call_delay_seconds: float | None,
    report_language: str | None,
    custom_user_prompt: str | None,
    credential_status_value: str,
) -> WorldlineGenerationConfig:
    return WorldlineGenerationConfig(
        worldline_provider=worldline_provider,
        worldline_chunk_days=chunk_days,
        llm_provider=llm_provider,
        llm_real_enabled=llm_real_enabled,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_max_output_tokens=llm_max_output_tokens,
        llm_call_delay_seconds=llm_call_delay_seconds,
        report_language=report_language,
        custom_user_prompt=custom_user_prompt,
        credential_status=credential_status_value,
    )


def _provenance(
    report: ScenarioReport,
    request: ScenarioWorldlineChunkRequest,
    *,
    provider: str,
    model: str | None,
    credential_status_value: str,
    network_call_performed: bool,
    input_context_hash: str,
    output_validation_status: str,
    safety_check_status: str,
    failed: bool,
    attempt_count: int,
    last_error: str | None,
    response_diagnostics: dict[str, object] | None = None,
) -> dict[str, Any]:
    previous = report.worldline_simulation.provenance if report.worldline_simulation else {}
    previous_consecutive_failures = _previous_consecutive_failed_chunk_count(report)
    consecutive_failures = previous_consecutive_failures + 1 if failed else 0
    generation_halted = consecutive_failures >= MAX_CONSECUTIVE_FAILED_CHUNKS
    halt_reason = (
        "LLM worldline generation stopped after two consecutive chunks failed after three attempts each."
        if generation_halted
        else None
    )
    chunk_entry = {
        "chunk_index": request.chunk_index,
        "total_chunks": request.total_chunks,
        "chunk_start_date": request.chunk_start_date.isoformat(),
        "chunk_end_date": request.chunk_end_date.isoformat(),
        "status": "fallback" if failed else "completed",
        "output_validation_status": output_validation_status,
        "safety_check_status": safety_check_status,
        "network_call_performed": network_call_performed,
        "attempt_count": attempt_count,
        "max_attempts": MAX_WORLDLINE_CHUNK_ATTEMPTS,
        "last_error": last_error,
        "response_diagnostics": response_diagnostics,
        "consecutive_failed_chunk_count": consecutive_failures,
        "generation_halted": generation_halted,
    }
    return {
        **previous,
        "generation_mode": "llm_chunk_v1",
        "provider": provider,
        "model": model,
        "prompt_template_version": WORLDLINE_PROMPT_TEMPLATE_VERSION,
        "chunk_size_days": request.worldline_chunk_days,
        "network_call_performed": bool(
            previous.get("network_call_performed") or network_call_performed
        ),
        "input_context_hash": input_context_hash,
        "output_validation_status": output_validation_status,
        "safety_check_status": safety_check_status,
        "credential_status": credential_status_value,
        "attempt_count": attempt_count,
        "max_attempts": MAX_WORLDLINE_CHUNK_ATTEMPTS,
        "last_error": last_error,
        "response_diagnostics": response_diagnostics,
        "chunk_count": _previous_chunk_count(report) + 1,
        "failed_chunk_count": _previous_failed_chunk_count(report) + (1 if failed else 0),
        "consecutive_failed_chunk_count": consecutive_failures,
        "generation_halted": generation_halted,
        "halt_reason": halt_reason,
        "llm_output_quality_notes": _merge_strings(
            _string_list(previous.get("llm_output_quality_notes")),
            _quality_notes_for_status(
                status="fallback" if failed else "completed",
                output_validation_status=output_validation_status,
                safety_check_status=safety_check_status,
                caveat=(
                    "Chunk used deterministic fallback."
                    if failed
                    else f"Chunk output parsed as valid JSON and passed safety review on attempt {attempt_count}."
                ),
            ),
        ),
        "chunk_history": _merge_chunk_history(previous.get("chunk_history"), chunk_entry),
    }


def _previous_chunk_count(report: ScenarioReport) -> int:
    try:
        return int((report.worldline_simulation.provenance if report.worldline_simulation else {}).get("chunk_count", 0))
    except (TypeError, ValueError):
        return 0


def _previous_failed_chunk_count(report: ScenarioReport) -> int:
    try:
        return int((report.worldline_simulation.provenance if report.worldline_simulation else {}).get("failed_chunk_count", 0))
    except (TypeError, ValueError):
        return 0


def _previous_consecutive_failed_chunk_count(report: ScenarioReport) -> int:
    provenance = report.worldline_simulation.provenance if report.worldline_simulation else {}
    stored = provenance.get("consecutive_failed_chunk_count")
    if stored is not None:
        try:
            return max(0, int(stored))
        except (TypeError, ValueError):
            pass

    count = 0
    history = provenance.get("chunk_history")
    if isinstance(history, list):
        for item in reversed(history):
            if not isinstance(item, dict) or item.get("status") != "fallback":
                break
            count += 1
    return count


def _generation_circuit_is_open(
    report: ScenarioReport,
    request: ScenarioWorldlineChunkRequest,
) -> bool:
    simulation = report.worldline_simulation
    if simulation is None or not simulation.provenance.get("generation_halted"):
        return False
    history = simulation.provenance.get("chunk_history")
    if not isinstance(history, list) or not history:
        return True
    last_entry = history[-1]
    if not isinstance(last_entry, dict):
        return True
    try:
        return request.chunk_index > int(last_entry.get("chunk_index", 0))
    except (TypeError, ValueError):
        return True


def _halted_generation(
    report: ScenarioReport,
    generation_config: WorldlineGenerationConfig,
) -> WorldlineSimulation:
    simulation = report.worldline_simulation
    if simulation is None:
        raise ValueError("worldline simulation is unavailable")
    reason = str(
        simulation.provenance.get("halt_reason")
        or "LLM worldline generation is halted after consecutive chunk failures."
    )
    return simulation.model_copy(
        update={
            "status": "halted",
            "summary": reason,
            "caveats": _merge_strings(simulation.caveats, [reason]),
            "provenance": {
                **simulation.provenance,
                "generation_halted": True,
                "halt_reason": reason,
                "network_call_performed": simulation.provenance.get(
                    "network_call_performed", False
                ),
            },
            "generation_config": simulation.generation_config or generation_config,
        }
    )


def _clamp_float(value: Any, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = fallback
    return round(max(0.0, min(1.0, numeric)), 3)


def _string_list(value: Any) -> list[str]:
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
            if item not in seen:
                merged.append(item)
                seen.add(item)
    return merged


def _mark_day(
    day: WorldlineDay,
    *,
    generation_source: str,
    chunk_index: int | None,
    chunk_status: str,
    quality_notes: list[str],
) -> WorldlineDay:
    return day.model_copy(
        update={
            "generation_source": generation_source,
            "chunk_index": chunk_index,
            "chunk_status": chunk_status,
            "quality_notes": _merge_strings(day.quality_notes, quality_notes),
        }
    )


def _mark_days_for_status(
    days: list[WorldlineDay],
    *,
    status: str,
    mode: str,
    chunk_index: int | None,
    output_validation_status: str,
    caveat: str,
) -> list[WorldlineDay]:
    if mode != "llm_chunk_v1":
        return days
    source = "fallback" if status in {"dry_run", "fallback"} else "llm_chunk"
    return [
        _mark_day(
            day,
            generation_source=source,
            chunk_index=chunk_index,
            chunk_status=output_validation_status,
            quality_notes=[caveat],
        )
        for day in days
    ]


def _quality_notes_for_status(
    *,
    status: str,
    output_validation_status: str,
    safety_check_status: str,
    caveat: str,
) -> list[str]:
    return [
        f"Status: {status}.",
        f"Output validation: {output_validation_status}.",
        f"Safety check: {safety_check_status}.",
        caveat,
    ]


def _merge_chunk_history(value: Any, entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    history = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    if entry is not None:
        history.append(entry)
    return history
