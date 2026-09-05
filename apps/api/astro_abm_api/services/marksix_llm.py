from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from astro_abm.marksix import _next_draw_dates
from astro_abm.marksix_astro import (
    analyze_moon_phase_numbers,
    analyze_retrograde_numbers,
    planetary_snapshot,
)
from astro_abm_api.models.marksix import MarkSixLlmWorldlineRequest
from astro_abm_api.services.llm_client import _call_openai_compatible, build_llm_config, parse_llm_json


def _history_context(request: MarkSixLlmWorldlineRequest, snapshot: dict[str, Any]) -> dict[str, Any]:
    if request.astro_context_type == "moon_phase":
        analysis = analyze_moon_phase_numbers(condition=str(snapshot["moon_phase_zone"]))
    else:
        body_snapshot = next(item for item in snapshot["planets"] if item["body"] == request.astro_body)
        analysis = analyze_retrograde_numbers(body=request.astro_body, condition=str(body_snapshot["motion_phase"]))
    ranked = sorted(analysis["numbers"], key=lambda row: row["lift"] or 0, reverse=True)
    return {
        "context_type": analysis["context_type"], "body": analysis["body"],
        "condition": analysis["condition"], "rule_era": analysis["rule_era"],
        "coverage": {"start": analysis["start_date"], "end": analysis["end_date"]},
        "sample_counts": {
            "total_draws": analysis["total_draws"],
            "condition_draws": analysis["condition_draws"],
            "baseline_draws": analysis["baseline_draws"],
        },
        "number_statistics": [
            {
                "number": row["number"], "lift": round(row["lift"], 4) if row["lift"] is not None else None,
                "rate_difference_pct_points": round(row["rate_difference"] * 100, 4),
                "q_value_fdr": round(row["q_value_fdr"], 4),
            }
            for row in ranked
        ],
    }


def _messages(*, context: dict[str, Any], language: str) -> list[dict[str, str]]:
    requested_language = "Traditional Chinese" if language == "zh-Hant" else "English"
    return [
        {
            "role": "system",
            "content": (
                "You create an entertainment-only Hong Kong Mark Six scenario guess from the supplied next-draw "
                "planetary snapshot and historical association comparison. Historical lift is descriptive and does "
                "not establish predictive power. Do not invent astronomy or draw history. Return strict JSON only "
                "with keys numbers (six unique integers 1-49), extra_number (a different integer 1-49), rationale "
                f"(string), confidence (string), and caveats (array of strings). Write text in {requested_language}."
            ),
        },
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, separators=(",", ":"))},
    ]


def _validated_numbers(payload: dict[str, Any]) -> tuple[list[int], int]:
    numbers = payload.get("numbers")
    extra = payload.get("extra_number")
    if not isinstance(numbers, list) or len(numbers) != 6 or not all(isinstance(value, int) for value in numbers):
        raise ValueError("LLM output must contain six integer main numbers")
    if not isinstance(extra, int):
        raise ValueError("LLM output must contain one integer extra number")
    values = [*numbers, extra]
    if len(set(values)) != 7 or any(value < 1 or value > 49 for value in values):
        raise ValueError("LLM numbers must be seven unique values from 1 to 49")
    return sorted(numbers), extra


def generate_marksix_llm_worldline(request: MarkSixLlmWorldlineRequest) -> dict[str, Any]:
    next_draw_date = _next_draw_dates(datetime.now(UTC).date() + timedelta(days=1), 1)[0]
    next_draw_snapshot = planetary_snapshot(next_draw_date)
    context = {
        "purpose": "entertainment_mark_six_worldline_guess",
        "next_draw": next_draw_snapshot,
        "historical_comparison": _history_context(request, next_draw_snapshot),
        "interpretation_boundary": (
            "Historical associations and LLM output do not change the equal probability of valid combinations."
        ),
    }
    config = build_llm_config(
        provider="openai_compatible", base_url=request.base_url, model=request.model,
        api_key=request.api_key, real_enabled=True, timeout_seconds=request.timeout_seconds,
        max_output_tokens=3000,
    )
    raw_text = _call_openai_compatible(config, _messages(context=context, language=request.language), max_tokens=3000)
    payload = parse_llm_json(raw_text)
    if payload is None:
        raise ValueError("The LLM response was not valid JSON")
    numbers, extra_number = _validated_numbers(payload)
    disclaimer = (
        "LLM 僅根據所提供的天象與歷史比較作娛樂猜測；真實六合彩每個合法組合的機率相同。非投注建議，只限18歲或以上人士。"
        if request.language == "zh-Hant" else
        "The LLM made an entertainment guess only from the supplied astronomy and historical comparison; every valid combination remains equally probable. Not betting advice. Adults 18+ only."
    )
    digest = hashlib.sha256(f"{next_draw_date}:{numbers}:{extra_number}:{request.model}".encode()).hexdigest()[:10]
    return {
        "worldline": {
            "worldline_id": f"marksix-llm-{digest}", "generation_mode": "llm_astro_entertainment_v1",
            "draws": [{"date": next_draw_date.isoformat(), "draw_index": 1, "numbers": numbers, "extra_number": extra_number}],
            "disclaimer": disclaimer,
            "astro_context": {
                "next_draw": context["next_draw"],
                "historical_comparison": context["historical_comparison"],
            },
        },
        "rationale": str(payload.get("rationale") or ""),
        "confidence": str(payload.get("confidence") or "unknown"),
        "caveats": [str(value) for value in payload.get("caveats", []) if isinstance(value, (str, int, float))],
        "provider": "openai_compatible", "model": request.model,
        "network_call_performed": True,
        "prompt_context": {
            "next_draw_date": next_draw_date.isoformat(),
            "astro_context_type": request.astro_context_type,
            "historical_condition": context["historical_comparison"]["condition"],
            "condition_draws": context["historical_comparison"]["sample_counts"]["condition_draws"],
            "credential_status": "redacted" if request.api_key else "not_configured",
        },
    }
