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
- daily_highlights: array of at most 5 objects with date, summary, key_context, agent_focus, caveats
- agent_interpretations: array of at most 1 object per agent with agent_id, agent_name, interpretation, risk_focus, caveats
- risk_themes: array of strings
- caveats: array of strings
- disclaimer: string

Keep the JSON compact and complete.
Make scenario_reading easy for a human to scan:
- Use 3 to 5 short lines separated by "\\n".
- Prefer Markdown-style bullets, for example "- Market setup: ...".
- Do not write one long paragraph.
- Avoid repeating the same disclaimer or placeholder warning in every sentence.
- If the context is a chunk, summarize only the supplied chunk dates.
For Traditional Chinese, use short Traditional Chinese bullet lines with clear labels such as:
"- 市場脈絡：..."
"- 代理反應：..."
"- 資料限制：..."
Do not include every day in daily_highlights; select representative days only.
For key_context, agent_focus, risk_focus, and caveats, always return arrays of short strings.
Do not wrap the JSON in Markdown fences.

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
