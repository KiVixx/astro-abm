from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from datetime import date

from astro_abm_api.models.report import DailyScenarioSnapshot, ScenarioReport


LLM_MAX_CONTEXT_DAYS_ENV = "ASTRO_ABM_LLM_MAX_CONTEXT_DAYS"
DEFAULT_MAX_CONTEXT_DAYS = 60


def configured_max_context_days() -> int:
    raw = os.getenv(LLM_MAX_CONTEXT_DAYS_ENV)
    if not raw:
        return DEFAULT_MAX_CONTEXT_DAYS
    try:
        return max(10, int(raw))
    except ValueError:
        return DEFAULT_MAX_CONTEXT_DAYS


def build_llm_context(
    report: ScenarioReport,
    *,
    max_context_days: int | None = None,
    selected_dates: set[date] | None = None,
    chunk_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    max_days = max_context_days or configured_max_context_days()
    timeline = (
        [snapshot for snapshot in report.daily_timeline if snapshot.date in selected_dates]
        if selected_dates is not None
        else report.daily_timeline
    )
    selected_days, compression_notes = select_context_days(timeline, max_days=max_days)
    context = {
        "title": report.title,
        "description": report.description,
        "date_range": {
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
        },
        "language": report.language or "en",
        "assets": report.assets,
        "asset_profiles": [
            {
                "asset": profile.asset,
                "label": profile.label,
                "series_type": profile.series_type,
                "supported": profile.supported,
                "market_daily_supported": profile.market_daily_supported,
                "notes": profile.notes,
            }
            for profile in report.asset_profiles
        ],
        "agents": [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "category": agent.category,
                "risk_tolerance": agent.risk_tolerance,
                "time_horizon": agent.time_horizon,
                "decision_style": agent.decision_style,
            }
            for agent in report.agents
        ],
        "coverage_summary": report.coverage_summary.model_dump(mode="json") if report.coverage_summary else None,
        "daily_timeline": [compact_daily_snapshot(snapshot) for snapshot in selected_days],
        "context_compression": {
            "original_days": len(timeline),
            "included_days": len(selected_days),
            "max_context_days": max_days,
            "notes": compression_notes,
        },
        "chunk_metadata": chunk_metadata,
        "risk_themes": report.risk_themes or report.risks,
        "caveats": report.caveats,
        "disclaimer": report.disclaimer,
        "safety_boundaries": [
            "association only",
            "scenario rehearsal only",
            "not financial advice",
            "not a trading signal",
            "do not invent missing data",
            "do not provide buy/sell/short/long recommendations",
            "do not provide price targets",
            "do not claim causality",
        ],
    }
    context["input_context_hash"] = hash_context(context)
    return context


def select_context_days(
    timeline: list[DailyScenarioSnapshot],
    *,
    max_days: int,
) -> tuple[list[DailyScenarioSnapshot], list[str]]:
    if len(timeline) <= max_days:
        return timeline, ["daily_timeline length is within context limit; all days included"]

    selected: dict[str, DailyScenarioSnapshot] = {}

    def add(snapshot: DailyScenarioSnapshot) -> None:
        selected[snapshot.date.isoformat()] = snapshot

    for snapshot in timeline[:5]:
        add(snapshot)
    for snapshot in timeline[-5:]:
        add(snapshot)
    for snapshot in timeline:
        if snapshot.research_signals.stress_regime == "stress":
            add(snapshot)
        if snapshot.research_signals.astro_activity in {"high", "elevated"} or snapshot.astro_context.intensity == "high":
            add(snapshot)
        if snapshot.data_coverage.source == "local_research_snapshot":
            add(snapshot)
        if len(selected) >= max_days:
            break

    ordered = sorted(selected.values(), key=lambda snapshot: snapshot.date)
    if len(ordered) > max_days:
        ordered = ordered[:max_days]
    return ordered, [
        "daily_timeline compressed for LLM context",
        "included first 5 days, last 5 days, stress days, high astro-activity days, and local research days where possible",
        "deduplicated by date",
    ]


def compact_daily_snapshot(snapshot: DailyScenarioSnapshot) -> dict[str, Any]:
    return {
        "date": snapshot.date.isoformat(),
        "summary": snapshot.daily_summary,
        "astro": {
            "summary": snapshot.astro_context.summary,
            "event_tags": snapshot.astro_context.event_tags,
            "intensity": snapshot.astro_context.intensity,
        },
        "market": {
            "summary": snapshot.market_context.summary,
            "stress_regime": snapshot.market_context.stress_regime,
            "volatility_regime": snapshot.market_context.volatility_regime,
            "liquidity_regime": snapshot.market_context.liquidity_regime,
        },
        "coverage": snapshot.data_coverage.model_dump(mode="json"),
        "research_signals": snapshot.research_signals.model_dump(mode="json"),
        "asset_contexts": [
            {
                "asset": context.asset,
                "series_type": context.series_type,
                "supported": context.supported,
                "market_daily": context.market_daily,
                "data_source": context.data_source,
                "data_quality": context.data_quality,
                "volatility_regime": context.volatility_regime,
                "stress_sentiment": context.stress_sentiment,
                "notes": context.notes[:3],
            }
            for context in snapshot.asset_contexts
        ],
        "agent_states": [
            {
                "agent_id": state.agent_id,
                "agent_name": state.agent_name,
                "mood": state.mood,
                "risk_appetite": state.risk_appetite,
                "likely_reaction": state.likely_reaction,
                "attention_triggers": state.attention_triggers[:6],
                "caveats": state.caveats,
            }
            for state in snapshot.agent_states
        ],
        "risk_themes": snapshot.daily_risk_themes,
        "caveats": snapshot.caveats,
        "disclaimer": snapshot.disclaimer,
    }


def hash_context(context: dict[str, Any]) -> str:
    payload = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
