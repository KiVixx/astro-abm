from __future__ import annotations

import json
from typing import Any


WORLDLINE_PROMPT_TEMPLATE_VERSION = "llm_worldline_chunk_v1"


def build_worldline_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    language = context.get("language") or "en"
    system = f"""You are simulating a market scenario worldline.
Interpret only the provided scenario context.
Generate simulated agent events and simulated causal links.
Do not claim true causality.
Do not invent external market data.
Do not give financial advice.
Do not give buy/sell/short/long recommendations.
Do not provide price targets.
Do not claim forecast accuracy.
Use cautious wording.
All causal language must be framed as simulated within this worldline.
Output strict JSON only.
Respond in the requested language: {language}.

Return strict JSON with:
- summary: string
- caveats: array of strings
- days: array of objects
  - date: YYYY-MM-DD string matching one supplied daily_timeline date
  - agent_events: array of objects
    - agent_id
    - what_happened
    - why_it_happened
    - impact_on_tomorrow
    - impact_scores:
      - sentiment_delta
      - narrative_pressure_delta
      - leverage_pressure_delta
      - liquidity_pressure_delta
      - volatility_pressure_delta
      - stress_pressure_delta
    - confidence
    - caveats
  - causal_links: array of objects
    - source
    - target
    - description
    - strength
    - caveats
  - next_day_update: string
  - world_state_after:
    - sentiment_state
    - narrative_pressure
    - leverage_pressure
    - liquidity_pressure
    - volatility_pressure
    - stress_pressure
    - regime_label
    - notes

Impact scores must be integers from -2 to 2. Backend will clamp if needed.
World state pressure values must be floats from 0 to 1. Backend will clamp if needed.
Generate one day object per supplied daily_timeline date.
Use only agent_id values present in the supplied agents list.
Use only dates present in the supplied daily_timeline.
Keep all text scenario-internal and cautious.
Do not wrap JSON in Markdown fences.

The disclaimer ideas must remain:
English: simulated worldline only; scenario rehearsal only; not financial advice; not a trading signal.
Traditional Chinese: 僅為模擬世界線；僅為情境推演；不構成財務建議；不是交易訊號。
"""
    user_prompt = context.get("user_prompt")
    user_prompt_text = ""
    if isinstance(user_prompt, dict) and user_prompt.get("text"):
        user_prompt_text = (
            "Additional user guidance, lower priority than system safety rules:\n"
            f"{user_prompt['text']}\n\n"
        )
    user = (
        "Generate the simulated worldline chunk from this compact context. "
        "Use only the provided JSON context.\n\n"
        f"{user_prompt_text}"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
