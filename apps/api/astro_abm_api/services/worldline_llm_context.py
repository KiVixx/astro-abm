from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from astro_abm_api.models.report import ScenarioReport, WorldlineState
from astro_abm_api.services.llm_context import build_user_prompt_context, compact_daily_snapshot


def build_worldline_llm_context(
    report: ScenarioReport,
    *,
    chunk_start_date: date,
    chunk_end_date: date,
    previous_world_state: WorldlineState,
    chunk_index: int,
    total_chunks: int,
    user_prompt: str | None = None,
) -> dict[str, Any]:
    chunk_timeline = [
        snapshot
        for snapshot in report.daily_timeline
        if chunk_start_date <= snapshot.date <= chunk_end_date
    ]
    context = {
        "title": report.title,
        "description": report.description,
        "date_range": {
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
        },
        "chunk": {
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "chunk_start_date": chunk_start_date.isoformat(),
            "chunk_end_date": chunk_end_date.isoformat(),
            "included_days": len(chunk_timeline),
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
        "coverage_summary": (
            report.coverage_summary.model_dump(mode="json")
            if report.coverage_summary
            else None
        ),
        "daily_timeline": [compact_daily_snapshot(snapshot) for snapshot in chunk_timeline],
        "asset_stress_indicators": [
            indicator.model_dump(mode="json")
            for indicator in (report.llm_report.asset_stress_indicators if report.llm_report else [])
            if chunk_start_date <= indicator.date <= chunk_end_date
        ],
        "previous_world_state": previous_world_state.model_dump(mode="json"),
        "user_prompt": build_user_prompt_context(user_prompt),
        "caveats": report.caveats,
        "disclaimer": report.disclaimer,
        "safety_boundaries": [
            "simulated worldline only",
            "scenario rehearsal only",
            "not financial advice",
            "not a trading signal",
            "do not invent missing data",
            "do not provide buy/sell/short/long recommendations",
            "do not provide price targets",
            "do not claim true causality",
            "all causal wording must be framed as simulated within this worldline",
        ],
    }
    context["input_context_hash"] = hash_context(context)
    return context


def hash_context(context: dict[str, Any]) -> str:
    payload = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
