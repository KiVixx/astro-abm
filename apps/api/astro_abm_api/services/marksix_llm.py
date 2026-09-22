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


DEFAULT_ASTRO_FEATURES = (
    "mercury_motion",
    "venus_motion",
    "mars_motion",
    "jupiter_motion",
    "saturn_motion",
    "uranus_motion",
    "neptune_motion",
    "pluto_motion",
    "moon_phase",
)
MOTION_FEATURE_BODIES = {
    "mercury_motion": "Mercury",
    "venus_motion": "Venus",
    "mars_motion": "Mars",
    "jupiter_motion": "Jupiter",
    "saturn_motion": "Saturn",
    "uranus_motion": "Uranus",
    "neptune_motion": "Neptune",
    "pluto_motion": "Pluto",
}
HISTORY_FEATURES = {
    "mercury_motion", "venus_motion", "mars_motion",
    "jupiter_motion", "saturn_motion", "moon_phase",
}
MAJOR_ASPECTS = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}


def _analysis_context(analysis: dict[str, Any]) -> dict[str, Any]:
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


def _history_context(request: MarkSixLlmWorldlineRequest, snapshot: dict[str, Any]) -> dict[str, Any]:
    if request.astro_context_type == "moon_phase":
        return _analysis_context(analyze_moon_phase_numbers(condition=str(snapshot["moon_phase_zone"])))
    body_snapshot = next(item for item in snapshot["planets"] if item["body"] == request.astro_body)
    return _analysis_context(
        analyze_retrograde_numbers(body=request.astro_body, condition=str(body_snapshot["motion_phase"]))
    )


def _major_aspects(snapshot: dict[str, Any], *, orb_deg: float = 6.0) -> list[dict[str, Any]]:
    planets = [*(snapshot.get("luminaries") or []), *snapshot["planets"]]
    aspects: list[dict[str, Any]] = []
    for index, body_a in enumerate(planets):
        for body_b in planets[index + 1:]:
            separation = abs((body_a["longitude_deg"] - body_b["longitude_deg"] + 180) % 360 - 180)
            aspect_name, aspect_deg = min(
                MAJOR_ASPECTS.items(),
                key=lambda item: abs(separation - item[1]),
            )
            delta = abs(separation - aspect_deg)
            if delta <= orb_deg:
                aspects.append({
                    "body_a": body_a["body"],
                    "body_b": body_b["body"],
                    "aspect": aspect_name,
                    "aspect_deg": aspect_deg,
                    "separation_deg": round(separation, 4),
                    "orb_deg": round(delta, 4),
                })
    return aspects


def _selected_astro_context(
    request: MarkSixLlmWorldlineRequest,
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    selected = list(request.astro_features or DEFAULT_ASTRO_FEATURES)
    selected_set = set(selected)
    context: dict[str, Any] = {
        "date": snapshot["date"],
        "sample_time": snapshot["sample_time"],
        "selected_astro_features": selected,
    }
    selected_bodies = {
        body for feature, body in MOTION_FEATURE_BODIES.items() if feature in selected_set
    }
    if selected_bodies:
        context["planet_motion"] = [
            row for row in snapshot["planets"] if row["body"] in selected_bodies
        ]
    if "moon_phase" in selected_set:
        context["moon_phase"] = {
            "angle_deg": snapshot["moon_phase_angle_deg"],
            "zone": snapshot["moon_phase_zone"],
            "luminaries": snapshot.get("luminaries") or [],
        }
    if "major_aspects" in selected_set:
        context["major_aspects"] = {
            "orb_limit_deg": 6.0,
            "pairs": _major_aspects(snapshot),
            "scope": "Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, and Pluto",
        }

    preferred = (
        "moon_phase"
        if request.astro_context_type == "moon_phase"
        else f"{request.astro_body.lower()}_motion"
    )
    primary = preferred if preferred in selected_set else next(
        (feature for feature in selected if feature in HISTORY_FEATURES),
        None,
    )
    history: dict[str, Any] | None = None
    if primary == "moon_phase":
        history = _analysis_context(
            analyze_moon_phase_numbers(condition=str(snapshot["moon_phase_zone"]))
        )
    elif primary in HISTORY_FEATURES and primary in MOTION_FEATURE_BODIES:
        body = MOTION_FEATURE_BODIES[primary]
        body_snapshot = next(item for item in snapshot["planets"] if item["body"] == body)
        history = _analysis_context(
            analyze_retrograde_numbers(body=body, condition=str(body_snapshot["motion_phase"]))
        )
    return context, history, selected


def _messages(*, context: dict[str, Any], language: str) -> list[dict[str, str]]:
    requested_language = "Traditional Chinese" if language == "zh-Hant" else "English"
    return [
        {
            "role": "system",
            "content": (
                "You create an entertainment-only Hong Kong Mark Six scenario guess from the supplied next-draw "
                "selected astro data package and optional historical association comparison. Treat astro sections "
                "that are absent as not requested and do not infer them. Historical lift is descriptive and does "
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
    astro_context, history_context, selected_features = _selected_astro_context(
        request, next_draw_snapshot,
    )
    context: dict[str, Any] = {
        "purpose": "entertainment_mark_six_worldline_guess",
        "next_draw_astro_context": astro_context,
        "interpretation_boundary": (
            "Historical associations and LLM output do not change the equal probability of valid combinations."
        ),
    }
    if history_context is not None:
        context["primary_historical_comparison"] = history_context
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
                "next_draw": astro_context,
                "historical_comparison": history_context,
            },
        },
        "rationale": str(payload.get("rationale") or ""),
        "confidence": str(payload.get("confidence") or "unknown"),
        "caveats": [str(value) for value in payload.get("caveats", []) if isinstance(value, (str, int, float))],
        "provider": "openai_compatible", "model": request.model,
        "network_call_performed": True,
        "prompt_context": {
            "next_draw_date": next_draw_date.isoformat(),
            "astro_context_type": history_context["context_type"] if history_context else "major_aspects_only",
            "historical_condition": history_context["condition"] if history_context else "not_applicable",
            "condition_draws": history_context["sample_counts"]["condition_draws"] if history_context else 0,
            "selected_astro_features": selected_features,
            "included_astro_sections": [
                key for key in ("planet_motion", "moon_phase", "major_aspects") if key in astro_context
            ],
            "credential_status": "redacted" if request.api_key else "not_configured",
        },
    }
