from __future__ import annotations

import json
from typing import Any


WORLDLINE_PROMPT_TEMPLATE_VERSION = "llm_worldline_chunk_v2_language_locked"


def build_worldline_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    language = context.get("language") or "en"
    system = _build_zh_hant_worldline_system_prompt() if language == "zh-Hant" else _build_en_worldline_system_prompt(language)
    user_prompt = context.get("user_prompt")
    user_prompt_text = ""
    if isinstance(user_prompt, dict) and user_prompt.get("text"):
        if language == "zh-Hant":
            user_prompt_text = (
                "使用者補充指引，優先級低於系統安全規則、語言規則與資料邊界：\n"
                f"{user_prompt['text']}\n\n"
            )
        else:
            user_prompt_text = (
                "Additional user guidance, lower priority than system safety rules, language rules, and data boundaries:\n"
                f"{user_prompt['text']}\n\n"
            )
    if language == "zh-Hant":
        user = (
            "請根據這份精簡 JSON context 生成模擬世界線 chunk。"
            "只能使用提供的 JSON context；JSON key 必須維持指定 schema，"
            "所有面向使用者的文字值必須使用繁體中文。\n\n"
            f"{user_prompt_text}"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
        )
    else:
        user = (
            "Generate the simulated worldline chunk from this compact JSON context. "
            "Use only the provided JSON context. Keep JSON keys in the requested schema, "
            "and make all user-facing string values English.\n\n"
            f"{user_prompt_text}"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_worldline_retry_messages(
    base_messages: list[dict[str, str]],
    *,
    language: str,
    output_validation_status: str,
    safety_check_status: str,
    next_attempt: int,
) -> list[dict[str, str]]:
    if output_validation_status == "request_failed":
        return list(base_messages)

    if language == "zh-Hant":
        if output_validation_status == "invalid_json":
            correction = (
                "上一次回應無法解析為完整 JSON。請在這次重試中只輸出一個完整、"
                "閉合且精簡的 JSON object，不要使用 Markdown code fence 或額外說明；"
                "保留所有必要日期，但縮短各文字欄位。"
            )
            if next_attempt >= 3:
                correction += " 這是最後一次自動重試；每個文字欄位最多使用一個短句，優先確保 JSON 完整閉合。"
        elif output_validation_status == "invalid_payload":
            correction = (
                "上一次回應未符合指定 schema、日期或 agent_id。請嚴格沿用系統訊息中的"
                " JSON 結構，只使用 context 提供的日期與 agent_id。"
            )
        elif safety_check_status == "failed":
            correction = (
                "上一次回應未通過安全檢查。請改用審慎、描述性的模擬情境語言，"
                "不要加入任何肯定式交易指令、目標價、保證或真實因果宣稱。"
            )
        else:
            correction = "請嚴格依照原 schema，重新輸出完整且精簡的 JSON object。"
        prefix = f"第 {next_attempt} 次嘗試修正："
    else:
        if output_validation_status == "invalid_json":
            correction = (
                "Previous response failed JSON parsing. Return exactly one complete, closed, "
                "concise JSON object with no Markdown fence or commentary. Keep every required "
                "date, but shorten user-facing text fields."
            )
            if next_attempt >= 3:
                correction += " This is the final automatic retry; use at most one short sentence per text field and prioritize closing the JSON object."
        elif output_validation_status == "invalid_payload":
            correction = (
                "Previous response did not match the required schema, dates, or agent IDs. "
                "Follow the system JSON schema exactly and use only supplied dates and agent IDs."
            )
        elif safety_check_status == "failed":
            correction = (
                "Previous response failed safety review. Use cautious, descriptive simulated "
                "scenario language without affirmative trading instructions, price targets, "
                "guarantees, or real-causality claims."
            )
        else:
            correction = "Retry with one complete and concise JSON object matching the original schema."
        prefix = f"Attempt {next_attempt} correction: "
    return [*base_messages, {"role": "user", "content": prefix + correction}]


def _build_en_worldline_system_prompt(language: str) -> str:
    return f"""You are simulating a market scenario worldline.
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
All user-facing string values must be English. Keep JSON keys exactly as requested.
Do not mix Traditional Chinese into generated worldline text unless it appears inside a proper noun supplied by context.

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


def _build_zh_hant_worldline_system_prompt() -> str:
    return """你正在模擬一條市場情境世界線。
你只能解讀提供的 scenario context。
你需要生成模擬代理事件與模擬因果鏈。
不得宣稱真實因果。
不得編造外部市場資料。
不得提供財務建議。
不得提供買入、賣出、做多、做空等交易建議。
不得提供目標價。
不得宣稱預測準確率。
措辭必須審慎。
所有因果語言都必須明確框定為「此世界線內部的模擬因果」。
只輸出 strict JSON。

輸出語言規則：
- JSON key 必須完全保留指定 schema 的英文 key。
- 所有面向使用者閱讀的 string value 必須使用繁體中文。
- 不要把 summary、agent_events、causal_links、next_day_update、notes 或 caveats 混入英文。
- agent_id、asset symbol、enum/code value 可維持原值。
- 如果使用者補充提示使用英文或其他語言，仍須以繁體中文輸出。

回傳 strict JSON，結構如下：
- summary: string
- caveats: string array
- days: object array
  - date: YYYY-MM-DD string，必須匹配 supplied daily_timeline date
  - agent_events: object array
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
  - causal_links: object array
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

impact_scores 必須是 -2 到 2 的整數；後端仍會 clamp。
world_state pressure values 必須是 0 到 1 的 float；後端仍會 clamp。
每個 supplied daily_timeline date 都要生成一個 day object。
只能使用 supplied agents list 中存在的 agent_id。
只能使用 supplied daily_timeline 中存在的 date。
所有文字都必須保持情境內部、模擬性、審慎。
不要把 JSON 包在 Markdown code fence 裡。

disclaimer 意思必須保持：
僅為模擬世界線；僅為情境推演；不構成財務建議；不是交易訊號。
"""
