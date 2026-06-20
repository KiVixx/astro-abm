from __future__ import annotations

from astro_abm_api.models.report import (
    DailyScenarioSnapshot,
    ScenarioReport,
    WorldlineAgentEvent,
    WorldlineCausalLink,
    WorldlineDay,
    WorldlineImpactScores,
    WorldlineSimulation,
    WorldlineState,
)


WORLDLINE_DISCLAIMER = (
    "Simulated worldline only; scenario rehearsal only; not financial advice; "
    "not a trading signal."
)


def clamp_pressure(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def clamp_delta(value: int) -> int:
    return max(-2, min(2, int(value)))


def generate_worldline_simulation(report: ScenarioReport) -> WorldlineSimulation | None:
    if not report.daily_timeline:
        return None

    agent_categories = {agent.agent_id: agent.category for agent in report.agents}
    asset_support_by_date = _asset_support_by_date(report)
    current_state = _initial_state(report.daily_timeline[0], asset_support_by_date)
    days: list[WorldlineDay] = []

    for index, snapshot in enumerate(report.daily_timeline):
        world_state_before = current_state
        agent_events = [
            _build_agent_event(
                snapshot,
                agent_state.agent_id,
                agent_state.agent_name,
                agent_categories.get(agent_state.agent_id, "unknown"),
                asset_support_by_date.get(snapshot.date.isoformat()),
            )
            for agent_state in snapshot.agent_states
        ]
        causal_links = _build_causal_links(snapshot, agent_events)
        world_state_after = _apply_events(
            world_state_before,
            snapshot,
            agent_events,
            asset_support_by_date.get(snapshot.date.isoformat()),
        )
        next_day_update = (
            "End of simulated horizon; no next day is generated."
            if index == len(report.daily_timeline) - 1
            else _next_day_update(snapshot, world_state_after)
        )
        days.append(
            WorldlineDay(
                date=snapshot.date,
                day_index=snapshot.day_index,
                input_context_summary=_input_context_summary(snapshot),
                world_state_before=world_state_before,
                agent_events=agent_events,
                causal_links=causal_links,
                next_day_update=next_day_update,
                world_state_after=world_state_after,
                disclaimer=WORLDLINE_DISCLAIMER,
            )
        )
        current_state = world_state_after

    return WorldlineSimulation(
        status="mock_completed",
        mode="deterministic_mock_v1",
        horizon_days=len(days),
        days=days,
        summary=(
            "Deterministic mock worldline built from daily timeline context, "
            "agent states, coverage signals, and available asset stress indicators."
        ),
        caveats=[
            "Simulated causal links are scenario mechanics, not evidence of true causality.",
            "Pressure updates are deterministic mock values for future rehearsal only.",
            "This layer does not fetch external data and does not call an LLM.",
        ],
        provenance={
            "engine": "worldline_deterministic_mock_v1",
            "generation_mode": "deterministic_mock_v1",
            "source": "scenario_daily_timeline",
            "provider": "mock",
            "model": None,
            "prompt_template_version": None,
            "chunk_size_days": None,
            "network_call_performed": False,
            "input_context_hash": "",
            "output_validation_status": "not_run",
            "safety_check_status": "not_run",
            "credential_status": "not_configured",
            "chunk_count": 0,
            "failed_chunk_count": 0,
            "external_calls": False,
        },
    )


def _asset_support_by_date(report: ScenarioReport) -> dict[str, float]:
    indicators = report.llm_report.asset_stress_indicators if report.llm_report else []
    values_by_date: dict[str, list[float]] = {}
    for indicator in indicators:
        values_by_date.setdefault(indicator.date.isoformat(), []).append(
            indicator.sentiment_stress_support
        )
    return {
        date_key: sum(values) / len(values)
        for date_key, values in values_by_date.items()
        if values
    }


def _initial_state(
    snapshot: DailyScenarioSnapshot,
    asset_support: dict[str, float],
) -> WorldlineState:
    stress = _pressure_from_regime(
        snapshot.research_signals.stress_regime,
        {"stress": 0.72, "elevated": 0.62, "watchful": 0.48, "calm": 0.3},
        default=0.42,
    )
    volatility = _pressure_from_regime(
        snapshot.research_signals.volatility_regime,
        {"expanded": 0.64, "normal": 0.42, "compressed": 0.28},
        default=0.4,
    )
    liquidity = _pressure_from_regime(
        snapshot.research_signals.liquidity_regime,
        {"thin": 0.68, "selective": 0.54, "orderly": 0.3},
        default=0.4,
    )
    support = asset_support.get(snapshot.date.isoformat(), 50.0)
    narrative = 0.45
    if snapshot.research_signals.astro_activity in {"high", "medium"}:
        narrative += 0.12
    if support < 35:
        narrative += 0.1
    elif support > 66:
        narrative -= 0.06
    return _state(
        narrative_pressure=narrative,
        leverage_pressure=0.4 + volatility * 0.2,
        liquidity_pressure=liquidity,
        volatility_pressure=volatility,
        stress_pressure=stress,
        notes=["Initial state seeded from daily research signals and asset support context."],
    )


def _pressure_from_regime(
    value: str,
    mapping: dict[str, float],
    *,
    default: float,
) -> float:
    return mapping.get(value, default)


def _build_agent_event(
    snapshot: DailyScenarioSnapshot,
    agent_id: str,
    agent_name: str,
    category: str,
    asset_support: float | None,
) -> WorldlineAgentEvent:
    context_scores = _context_scores(snapshot, asset_support)
    category_scores = _category_scores(category)
    scores = {
        key: clamp_delta(context_scores.get(key, 0) + category_scores.get(key, 0))
        for key in (
            "sentiment_delta",
            "narrative_pressure_delta",
            "leverage_pressure_delta",
            "liquidity_pressure_delta",
            "volatility_pressure_delta",
            "stress_pressure_delta",
        )
    }
    support_note = (
        "LLM asset support metric is available for this day."
        if asset_support is not None
        else "No LLM asset support metric is available for this day."
    )
    return WorldlineAgentEvent(
        agent_id=agent_id,
        agent_name=agent_name,
        what_happened=(
            f"{agent_name} reacted to {snapshot.research_signals.stress_regime} stress, "
            f"{snapshot.research_signals.volatility_regime} volatility, and "
            f"{snapshot.research_signals.liquidity_regime} liquidity in the simulated path."
        ),
        why_it_happened=(
            f"The daily context carried {snapshot.research_signals.data_quality} data quality "
            f"and astro activity {snapshot.research_signals.astro_activity}. {support_note}"
        ),
        impact_on_tomorrow=_impact_on_tomorrow(category, scores),
        impact_scores=WorldlineImpactScores(**scores),
        confidence="low_mock_confidence",
        caveats=[
            "Deterministic mock agent event; not an observed market action.",
            "Simulated causal link only; not true causality.",
        ],
    )


def _context_scores(
    snapshot: DailyScenarioSnapshot,
    asset_support: float | None,
) -> dict[str, int]:
    stress = snapshot.research_signals.stress_regime
    volatility = snapshot.research_signals.volatility_regime
    liquidity = snapshot.research_signals.liquidity_regime
    astro = snapshot.research_signals.astro_activity
    scores = {
        "sentiment_delta": 0,
        "narrative_pressure_delta": 0,
        "leverage_pressure_delta": 0,
        "liquidity_pressure_delta": 0,
        "volatility_pressure_delta": 0,
        "stress_pressure_delta": 0,
    }
    if stress == "stress":
        scores["stress_pressure_delta"] += 1
        scores["volatility_pressure_delta"] += 1
        scores["sentiment_delta"] += 1
    elif stress == "elevated":
        scores["stress_pressure_delta"] += 1
    if volatility == "expanded":
        scores["volatility_pressure_delta"] += 1
    elif volatility == "compressed":
        scores["volatility_pressure_delta"] -= 1
    if liquidity in {"thin", "selective"}:
        scores["liquidity_pressure_delta"] += 1
    if astro == "high":
        scores["narrative_pressure_delta"] += 1
    if asset_support is not None:
        if asset_support < 35:
            scores["sentiment_delta"] += 1
            scores["stress_pressure_delta"] += 1
        elif asset_support > 66:
            scores["sentiment_delta"] -= 1
            scores["stress_pressure_delta"] -= 1
    return scores


def _category_scores(category: str) -> dict[str, int]:
    if category == "retail":
        return {"narrative_pressure_delta": 1, "sentiment_delta": 1}
    if category == "trading":
        return {"leverage_pressure_delta": 1, "volatility_pressure_delta": 1}
    if category == "institutional":
        return {"stress_pressure_delta": 1, "liquidity_pressure_delta": 1}
    if category == "company_type":
        return {"liquidity_pressure_delta": 1, "sentiment_delta": 0}
    return {}


def _impact_on_tomorrow(category: str, scores: dict[str, int]) -> str:
    pressure_keys = [
        key.replace("_delta", "")
        for key, value in scores.items()
        if value > 0 and key != "sentiment_delta"
    ]
    if not pressure_keys:
        return "Sets up a steadier next-day rehearsal state with no major pressure increase."
    if category == "trading":
        return f"Sets up tomorrow with more attention to {', '.join(pressure_keys)}."
    if category == "retail":
        return f"Sets up tomorrow with more narrative sensitivity around {', '.join(pressure_keys)}."
    return f"Sets up tomorrow with more risk review around {', '.join(pressure_keys)}."


def _build_causal_links(
    snapshot: DailyScenarioSnapshot,
    agent_events: list[WorldlineAgentEvent],
) -> list[WorldlineCausalLink]:
    links = [
        WorldlineCausalLink(
            source="daily_context",
            target="agent_events",
            description=(
                "Daily stress, volatility, liquidity, and astro tags are mapped into "
                "simulated agent reactions."
            ),
            strength="medium",
            caveats=["Simulated causal link only; not evidence of true causality."],
        )
    ]
    if snapshot.research_signals.stress_regime in {"stress", "elevated"}:
        links.append(
            WorldlineCausalLink(
                source="stress_regime",
                target="next_day_stress_pressure",
                description="Elevated stress labels raise next-day stress pressure in the mock path.",
                strength="medium",
                caveats=["Scenario path mechanic only."],
            )
        )
    if any(event.impact_scores.narrative_pressure_delta > 0 for event in agent_events):
        links.append(
            WorldlineCausalLink(
                source="agent_narrative_reaction",
                target="next_day_narrative_pressure",
                description="Narrative-sensitive agent events increase tomorrow's narrative pressure.",
                strength="low_to_medium",
                caveats=["Future rehearsal only; not a trading signal."],
            )
        )
    return links


def _apply_events(
    state: WorldlineState,
    snapshot: DailyScenarioSnapshot,
    agent_events: list[WorldlineAgentEvent],
    asset_support: float | None,
) -> WorldlineState:
    total = {
        "sentiment_delta": 0,
        "narrative_pressure_delta": 0,
        "leverage_pressure_delta": 0,
        "liquidity_pressure_delta": 0,
        "volatility_pressure_delta": 0,
        "stress_pressure_delta": 0,
    }
    for event in agent_events:
        for key in total:
            total[key] += getattr(event.impact_scores, key)
    divisor = max(len(agent_events), 1)
    support_adjustment = 0.0
    if asset_support is not None:
        support_adjustment = (50.0 - asset_support) / 1000.0

    return _state(
        narrative_pressure=(
            state.narrative_pressure
            + total["narrative_pressure_delta"] / divisor * 0.05
            + support_adjustment
        ),
        leverage_pressure=state.leverage_pressure + total["leverage_pressure_delta"] / divisor * 0.045,
        liquidity_pressure=state.liquidity_pressure + total["liquidity_pressure_delta"] / divisor * 0.045,
        volatility_pressure=state.volatility_pressure + total["volatility_pressure_delta"] / divisor * 0.045,
        stress_pressure=state.stress_pressure + total["stress_pressure_delta"] / divisor * 0.045,
        notes=[
            f"Updated from {len(agent_events)} simulated agent events.",
            f"Daily context: stress={snapshot.research_signals.stress_regime}, "
            f"volatility={snapshot.research_signals.volatility_regime}, "
            f"liquidity={snapshot.research_signals.liquidity_regime}.",
        ],
    )


def _state(
    *,
    narrative_pressure: float,
    leverage_pressure: float,
    liquidity_pressure: float,
    volatility_pressure: float,
    stress_pressure: float,
    notes: list[str],
) -> WorldlineState:
    values = {
        "narrative_pressure": clamp_pressure(narrative_pressure),
        "leverage_pressure": clamp_pressure(leverage_pressure),
        "liquidity_pressure": clamp_pressure(liquidity_pressure),
        "volatility_pressure": clamp_pressure(volatility_pressure),
        "stress_pressure": clamp_pressure(stress_pressure),
    }
    average_pressure = sum(values.values()) / len(values)
    if average_pressure >= 0.66:
        sentiment_state = "stressed"
    elif average_pressure >= 0.45:
        sentiment_state = "watchful"
    else:
        sentiment_state = "calm"
    return WorldlineState(
        sentiment_state=sentiment_state,
        regime_label=_regime_label(values),
        notes=notes,
        **values,
    )


def _regime_label(values: dict[str, float]) -> str:
    if values["stress_pressure"] >= 0.65 and values["liquidity_pressure"] >= 0.55:
        return "stress_liquidity_watch"
    if values["volatility_pressure"] >= 0.65:
        return "volatility_expansion_watch"
    if values["narrative_pressure"] >= 0.65:
        return "narrative_pressure_watch"
    return "balanced_rehearsal_path"


def _input_context_summary(snapshot: DailyScenarioSnapshot) -> str:
    return (
        f"{snapshot.date.isoformat()} context: stress={snapshot.research_signals.stress_regime}, "
        f"volatility={snapshot.research_signals.volatility_regime}, "
        f"liquidity={snapshot.research_signals.liquidity_regime}, "
        f"astro_activity={snapshot.research_signals.astro_activity}, "
        f"data_quality={snapshot.research_signals.data_quality}."
    )


def _next_day_update(snapshot: DailyScenarioSnapshot, state: WorldlineState) -> str:
    return (
        f"The next simulated day starts from {state.sentiment_state} sentiment with "
        f"regime label {state.regime_label}; prior day {snapshot.date.isoformat()} "
        "sets the rehearsal baseline for agent attention."
    )
