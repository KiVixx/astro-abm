from __future__ import annotations

import json
from typing import Any


PROMPT_TEMPLATE_VERSION = "llm_scenario_report_v1"


def build_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    language = context.get("language") or "en"
    system = f"""You are an analyst for a scenario rehearsal system.
Interpret only the provided context.
Do not invent missing data.
Do not claim causality.
Do not give financial advice.
Do not provide buy/sell/short/long recommendations.
Do not provide price targets.
Do not claim prediction accuracy.
Use cautious wording.
Keep outputs association-only and scenario-rehearsal-only.
The requested output language is: {language}.

Return strict JSON only, with these keys:
- executive_summary: string
- scenario_reading: string
- daily_highlights: array of objects with date, summary, key_context, agent_focus, caveats
- agent_interpretations: array of objects with agent_id, agent_name, interpretation, risk_focus, caveats
- risk_themes: array of strings
- caveats: array of strings
- disclaimer: string

The disclaimer must include these exact ideas:
English: association only; scenario rehearsal only; not financial advice; not a trading signal.
Traditional Chinese: 僅為相關性分析；僅為情境推演；不構成財務建議；不是交易訊號。
"""
    user = (
        "Build a cautious scenario narrative from this compact context. "
        "Use only the provided JSON context.\n\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
