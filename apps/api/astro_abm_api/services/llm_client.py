from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import requests
from dotenv import load_dotenv

from astro_abm_api.models.llm import LLMProvider, LLMTestRequest, LLMTestResponse
from astro_abm_api.models.report import (
    LlmAgentInterpretation,
    LlmAssetStressIndicator,
    LlmDailyHighlight,
    LlmReportProvenance,
    LlmScenarioReport,
    ScenarioReport,
)
from astro_abm_api.models.scenario import ScenarioCreateRequest
from astro_abm_api.models.scenario import ScenarioLlmChunkRequest
from astro_abm_api.services.llm_context import build_llm_context
from astro_abm_api.services.llm_prompts import PROMPT_TEMPLATE_VERSION, build_messages


load_dotenv()

ENABLE_REAL_LLM_ENV = "ASTRO_ABM_ENABLE_REAL_LLM"
LLM_API_KEY_ENV = "ASTRO_ABM_LLM_API_KEY"
LLM_BASE_URL_ENV = "ASTRO_ABM_LLM_BASE_URL"
LLM_MODEL_ENV = "ASTRO_ABM_LLM_MODEL"
LLM_TIMEOUT_ENV = "ASTRO_ABM_LLM_TIMEOUT_SECONDS"
LLM_MAX_OUTPUT_TOKENS_ENV = "ASTRO_ABM_LLM_MAX_OUTPUT_TOKENS"

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_OUTPUT_TOKENS = 5000
RAW_TEXT_PREVIEW_LIMIT = 800

BANNED_SAFETY_PATTERNS = (
    r"\bmust\s+buy\b",
    r"\bmust\s+sell\b",
    r"\byou\s+should\s+buy\b",
    r"\byou\s+should\s+sell\b",
    r"\byou\s+should\s+short\b",
    r"\byou\s+should\s+go\s+long\b",
    r"\bgo\s+long\b",
    r"\benter\s+long\b",
    r"\bgo\s+short\b",
    r"\benter\s+short\b",
    r"\blong\s+(btc|eth|sol|xrp|bnb|doge|ada|spx|ndx|gold|dxy|vix|us10y)\b",
    r"\bshort\s+(btc|eth|sol|xrp|bnb|doge|ada|spx|ndx|gold|dxy|vix|us10y)\b",
    r"\bbuy\s+(btc|eth|sol|xrp|bnb|doge|ada|spx|ndx|gold|dxy|vix|us10y)\b",
    r"\bsell\s+(btc|eth|sol|xrp|bnb|doge|ada|spx|ndx|gold|dxy|vix|us10y)\b",
    r"you should buy",
    r"you should sell",
    r"you should short",
    r"you should go long",
    r"\bbuy signal\b",
    r"\bsell signal\b",
    r"\bshort signal\b",
    r"\blong signal\b",
    r"price target",
    r"trading recommendation",
    r"guaranteed",
    r"predicts with certainty",
    r"\bcaused\b",
    r"\bcauses\b",
    r"will rise",
    r"will fall",
)

CHINESE_TRADING_INSTRUCTION_TERMS = (
    "買入",
    "賣出",
    "做多",
    "做空",
    "目標價",
    "保證",
    "一定會漲",
    "一定會跌",
)
CHINESE_SAFETY_CONTEXT_PATTERN = re.compile(
    r"不構成|不得(?:提供)?|不應(?:提供)?|不會|不能|不提供|未提供|"
    r"沒有|並非|不是|勿|禁止|避免|不保證"
)
CHINESE_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,；;。.!?\n]|但|然而|可是")


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider = "mock"
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    real_enabled: bool | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @property
    def real_calls_enabled(self) -> bool:
        if self.real_enabled is not None:
            return self.real_enabled
        return os.getenv(ENABLE_REAL_LLM_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def build_llm_config(
    provider: LLMProvider = "mock",
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    real_enabled: bool | None = None,
    timeout_seconds: float | None = None,
    max_output_tokens: int | None = None,
) -> LLMConfig:
    return LLMConfig(
        provider=provider,
        base_url=(base_url or os.getenv(LLM_BASE_URL_ENV) or None),
        model=(model or os.getenv(LLM_MODEL_ENV) or None),
        api_key=(api_key or os.getenv(LLM_API_KEY_ENV) or None),
        real_enabled=real_enabled,
        timeout_seconds=_timeout_seconds(timeout_seconds),
        max_output_tokens=_max_output_tokens(max_output_tokens),
    )


def provenance_for_llm(config: LLMConfig) -> dict[str, object]:
    return {
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "credential_status": credential_status(config),
        "network_call_performed": False,
    }


def generate_llm_scenario_report(
    request: ScenarioCreateRequest,
    report: ScenarioReport,
) -> LlmScenarioReport | None:
    if request.llm_provider == "mock":
        return None

    config = build_llm_config(
        provider=request.llm_provider,
        base_url=request.llm_base_url,
        model=request.llm_model,
        api_key=request.llm_api_key,
        real_enabled=request.llm_real_enabled,
        timeout_seconds=request.llm_timeout_seconds,
        max_output_tokens=request.llm_max_output_tokens,
    )
    context = build_llm_context(report, user_prompt=request.llm_user_prompt)
    context_hash = str(context["input_context_hash"])
    provenance = _provenance(
        config,
        input_context_hash=context_hash,
        network_call_performed=False,
        output_validation_status="not_run",
        safety_check_status="not_run",
    )

    if not config.real_calls_enabled:
        return _status_report(
            status="dry_run",
            config=config,
            provenance=provenance,
            executive_summary="Real LLM calls are disabled. Set ASTRO_ABM_ENABLE_REAL_LLM=1 to enable.",
            scenario_reading="No external LLM network call was performed. The deterministic scenario report remains the source of generated content.",
            language=request.language,
        )
    if not config.base_url or not config.model:
        return _status_report(
            status="failed",
            config=config,
            provenance=provenance.model_copy(update={"output_validation_status": "configuration_missing"}),
            executive_summary="OpenAI-compatible LLM provider is missing base_url or model.",
            scenario_reading="Configure ASTRO_ABM_LLM_BASE_URL and ASTRO_ABM_LLM_MODEL, or pass request-level base URL and model.",
            language=request.language,
        )

    try:
        raw_text = _call_openai_compatible(config, build_messages(context))
    except requests.RequestException as exc:
        return _status_report(
            status="failed",
            config=config,
            provenance=_provenance(
                config,
                input_context_hash=context_hash,
                network_call_performed=True,
                output_validation_status="request_failed",
                safety_check_status="not_run",
            ),
            executive_summary="The OpenAI-compatible LLM request failed safely.",
            scenario_reading=f"{type(exc).__name__}: {exc}",
            language=request.language,
        )

    parsed = parse_llm_json(raw_text)
    if parsed is None:
        return _status_report(
            status="invalid_output",
            config=config,
            provenance=_provenance(
                config,
                input_context_hash=context_hash,
                network_call_performed=True,
                output_validation_status="invalid_json",
                safety_check_status="not_run",
            ),
            executive_summary="The LLM returned output that could not be parsed as strict JSON.",
            scenario_reading="The raw output preview is retained for debugging without exposing credentials.",
            raw_text_preview=_preview(raw_text),
            language=request.language,
        )

    report_candidate = build_report_from_payload(
        parsed,
        language=request.language,
        config=config,
        provenance=_provenance(
            config,
            input_context_hash=context_hash,
            network_call_performed=True,
            output_validation_status="valid_json",
            safety_check_status="pending",
        ),
        raw_text_preview=_preview(raw_text),
    )
    if not safety_check_text(report_candidate.model_dump_json()):
        return report_candidate.model_copy(
            update={
                "status": "safety_review_failed",
                "executive_summary": "The LLM output failed safety review.",
                "scenario_reading": "The generated text contained restricted trading, causal, or certainty language and was not accepted.",
                "daily_highlights": [],
                "agent_interpretations": [],
                "asset_stress_indicators": [],
                "risk_themes": [],
                "provenance": report_candidate.provenance.model_copy(update={"safety_check_status": "failed"}),
            }
        )
    return report_candidate.model_copy(
        update={
            "status": "completed",
            "scenario_reading": _normalize_multiline_text(report_candidate.scenario_reading),
            "provenance": report_candidate.provenance.model_copy(update={"safety_check_status": "passed"}),
        }
    )


def generate_llm_scenario_report_chunk(
    request: ScenarioLlmChunkRequest,
    report: ScenarioReport,
) -> LlmScenarioReport:
    config = build_llm_config(
        provider=request.llm_provider,
        base_url=request.llm_base_url,
        model=request.llm_model,
        api_key=request.llm_api_key,
        real_enabled=request.llm_real_enabled,
        timeout_seconds=request.llm_timeout_seconds,
        max_output_tokens=request.llm_max_output_tokens,
    )
    selected_dates = _date_range(request.chunk_start_date, request.chunk_end_date)
    context = build_llm_context(
        report,
        selected_dates=selected_dates,
        max_context_days=max(10, len(selected_dates)),
        user_prompt=request.llm_user_prompt,
        chunk_metadata={
            "chunk_index": request.chunk_index,
            "total_chunks": request.total_chunks,
            "chunk_start_date": request.chunk_start_date.isoformat(),
            "chunk_end_date": request.chunk_end_date.isoformat(),
            "instruction": "Generate narrative only for this chunk's dates.",
        },
    )
    context_hash = str(context["input_context_hash"])
    provenance = _provenance(
        config,
        input_context_hash=context_hash,
        network_call_performed=False,
        output_validation_status="not_run",
        safety_check_status="not_run",
    )

    if not config.real_calls_enabled:
        return _status_report(
            status="dry_run",
            config=config,
            provenance=provenance,
            executive_summary="Real LLM calls are disabled. Set ASTRO_ABM_ENABLE_REAL_LLM=1 to enable.",
            scenario_reading="No external LLM network call was performed for this chunk.",
            language=request.language,
        )
    if not config.base_url or not config.model:
        return _status_report(
            status="failed",
            config=config,
            provenance=provenance.model_copy(update={"output_validation_status": "configuration_missing"}),
            executive_summary="OpenAI-compatible LLM provider is missing base_url or model.",
            scenario_reading="Configure the LLM base URL and model before generating chunks.",
            language=request.language,
        )

    try:
        raw_text = _call_openai_compatible(config, build_messages(context))
    except requests.RequestException as exc:
        return _status_report(
            status="failed",
            config=config,
            provenance=_provenance(
                config,
                input_context_hash=context_hash,
                network_call_performed=True,
                output_validation_status="request_failed",
                safety_check_status="not_run",
            ),
            executive_summary="The OpenAI-compatible LLM request failed safely.",
            scenario_reading=f"{type(exc).__name__}: {exc}",
            language=request.language,
        )

    parsed = parse_llm_json(raw_text)
    if parsed is None:
        return _status_report(
            status="invalid_output",
            config=config,
            provenance=_provenance(
                config,
                input_context_hash=context_hash,
                network_call_performed=True,
                output_validation_status="invalid_json",
                safety_check_status="not_run",
            ),
            executive_summary="The LLM returned output that could not be parsed as strict JSON.",
            scenario_reading="The raw output preview is retained for debugging without exposing credentials.",
            raw_text_preview=_preview(raw_text),
            language=request.language,
        )

    report_candidate = build_report_from_payload(
        parsed,
        language=request.language,
        config=config,
        provenance=_provenance(
            config,
            input_context_hash=context_hash,
            network_call_performed=True,
            output_validation_status="valid_json",
            safety_check_status="pending",
        ),
        raw_text_preview=_preview(raw_text),
    )
    if not safety_check_text(report_candidate.model_dump_json()):
        return report_candidate.model_copy(
            update={
                "status": "safety_review_failed",
                "executive_summary": "The LLM output failed safety review.",
                "scenario_reading": "The generated text contained restricted trading, causal, or certainty language and was not accepted.",
                "daily_highlights": [],
                "agent_interpretations": [],
                "asset_stress_indicators": [],
                "risk_themes": [],
                "provenance": report_candidate.provenance.model_copy(update={"safety_check_status": "failed"}),
            }
        )
    readable_reading = _format_chunk_scenario_reading(
        report_candidate.scenario_reading,
        start_date=request.chunk_start_date,
        end_date=request.chunk_end_date,
        language=request.language,
    )
    return report_candidate.model_copy(
        update={
            "status": "completed",
            "scenario_reading": readable_reading,
            "provenance": report_candidate.provenance.model_copy(update={"safety_check_status": "passed"}),
        }
    )


def merge_llm_report_chunk(
    existing: LlmScenarioReport | None,
    chunk: LlmScenarioReport,
) -> LlmScenarioReport:
    if chunk.status != "completed":
        return chunk
    if existing is None or existing.status != "completed":
        return chunk

    highlights_by_date = {
        item.date.isoformat(): item for item in existing.daily_highlights
    }
    for item in chunk.daily_highlights:
        highlights_by_date[item.date.isoformat()] = item
    agent_by_id = {
        item.agent_id: item for item in existing.agent_interpretations
    }
    for item in chunk.agent_interpretations:
        agent_by_id.setdefault(item.agent_id, item)
    indicators_by_key = {
        (item.date.isoformat(), item.asset): item
        for item in existing.asset_stress_indicators
    }
    for item in chunk.asset_stress_indicators:
        indicators_by_key[(item.date.isoformat(), item.asset)] = item

    return existing.model_copy(
        update={
            "scenario_reading": _merge_scenario_readings(
                existing.scenario_reading,
                chunk.scenario_reading,
            ),
            "daily_highlights": [
                highlights_by_date[key] for key in sorted(highlights_by_date)
            ],
            "agent_interpretations": list(agent_by_id.values()),
            "asset_stress_indicators": [
                indicators_by_key[key] for key in sorted(indicators_by_key)
            ],
            "risk_themes": _merge_string_lists(existing.risk_themes, chunk.risk_themes),
            "caveats": _merge_string_lists(existing.caveats, chunk.caveats),
            "raw_text_preview": chunk.raw_text_preview,
            "provenance": chunk.provenance,
        }
    )


def _merge_scenario_readings(existing: str, chunk: str) -> str:
    parts = [part.strip() for part in (existing, chunk) if part and part.strip()]
    return "\n\n".join(parts)


def _format_chunk_scenario_reading(
    reading: str,
    *,
    start_date: date,
    end_date: date,
    language: str,
) -> str:
    cleaned = _normalize_multiline_text(reading)
    if not cleaned:
        return ""
    date_label = (
        f"{start_date.isoformat()} 至 {end_date.isoformat()}"
        if language == "zh-Hant"
        else f"{start_date.isoformat()} to {end_date.isoformat()}"
    )
    heading = f"#### {date_label}"
    return f"{heading}\n{cleaned}"


def _normalize_multiline_text(value: str) -> str:
    lines = [line.strip() for line in value.replace("\r\n", "\n").split("\n")]
    normalized = [line for line in lines if line]
    if len(normalized) <= 1:
        return value.strip()
    return "\n".join(normalized)


def test_llm_connection(request: LLMTestRequest) -> LLMTestResponse:
    config = build_llm_config(
        provider=request.provider,
        base_url=request.base_url,
        model=request.model,
        api_key=request.api_key,
        real_enabled=request.real_enabled,
        timeout_seconds=request.timeout_seconds,
        max_output_tokens=request.max_output_tokens,
    )
    if config.provider == "mock":
        return LLMTestResponse(
            provider="mock",
            reachable=True,
            dry_run=True,
            status="ok",
            message="Mock LLM provider is available. No network call was made.",
            base_url=None,
            model="mock-deterministic",
        )

    if not config.real_calls_enabled:
        return LLMTestResponse(
            provider="openai_compatible",
            reachable=False,
            dry_run=True,
            status="disabled",
            message="Real LLM calls are disabled. Set ASTRO_ABM_ENABLE_REAL_LLM=1 to enable.",
            base_url=config.base_url,
            model=config.model,
        )
    if not config.base_url or not config.model:
        return LLMTestResponse(
            provider="openai_compatible",
            reachable=False,
            dry_run=False,
            status="configuration_missing",
            message="OpenAI-compatible provider is not configured. Provide base_url and model.",
            base_url=config.base_url,
            model=config.model,
        )

    try:
        _call_openai_compatible(
            config,
            [
                {"role": "system", "content": "Return a short JSON object."},
                {"role": "user", "content": '{"ping": true}'},
            ],
            max_tokens=64,
        )
    except requests.RequestException as exc:
        return LLMTestResponse(
            provider="openai_compatible",
            reachable=False,
            dry_run=False,
            status="request_failed",
            message=f"{type(exc).__name__}: {exc}",
            base_url=config.base_url,
            model=config.model,
        )
    return LLMTestResponse(
        provider="openai_compatible",
        reachable=True,
        dry_run=False,
        status="ok",
        message="OpenAI-compatible provider responded to a minimal chat completion test.",
        base_url=config.base_url,
        model=config.model,
    )


def _call_openai_compatible(
    config: LLMConfig,
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
) -> str:
    assert config.base_url and config.model
    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens or config.max_output_tokens,
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=config.timeout_seconds)
    response.raise_for_status()
    body = response.json()
    return str(body["choices"][0]["message"]["content"])


def parse_llm_json(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    elif not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def build_report_from_payload(
    payload: dict[str, Any],
    *,
    language: str,
    config: LLMConfig,
    provenance: LlmReportProvenance,
    raw_text_preview: str | None,
) -> LlmScenarioReport:
    return LlmScenarioReport(
        status="completed",
        provider=config.provider,
        model=config.model,
        language=language,
        executive_summary=str(payload.get("executive_summary") or ""),
        scenario_reading=str(payload.get("scenario_reading") or ""),
        daily_highlights=_daily_highlights_from_payload(payload.get("daily_highlights", [])),
        agent_interpretations=_agent_interpretations_from_payload(
            payload.get("agent_interpretations", [])
        ),
        asset_stress_indicators=_asset_stress_indicators_from_payload(
            payload.get("asset_stress_indicators", [])
        ),
        risk_themes=_string_list(payload.get("risk_themes", [])),
        caveats=_string_list(payload.get("caveats", [])),
        disclaimer=str(payload.get("disclaimer") or _default_disclaimer(language)),
        raw_text_preview=raw_text_preview,
        provenance=provenance,
    )


def safety_check_text(text: str) -> bool:
    lowered = text.lower()
    if any(re.search(pattern, lowered) for pattern in BANNED_SAFETY_PATTERNS):
        return False
    return not _contains_unsafe_chinese_trading_language(text)


def _contains_unsafe_chinese_trading_language(text: str) -> bool:
    for clause in CHINESE_CLAUSE_SPLIT_PATTERN.split(text):
        matched_terms = [
            (clause.find(term), term)
            for term in CHINESE_TRADING_INSTRUCTION_TERMS
            if term in clause
        ]
        if not matched_terms:
            continue

        stripped_clause = clause.strip()
        if stripped_clause in CHINESE_TRADING_INSTRUCTION_TERMS:
            return True

        first_term_index = min(index for index, _ in matched_terms)
        safety_contexts = list(CHINESE_SAFETY_CONTEXT_PATTERN.finditer(clause))
        has_nearby_safety_context = any(
            context.start() <= first_term_index
            and first_term_index - context.end() <= 24
            for context in safety_contexts
        )
        if not has_nearby_safety_context:
            return True
    return False


def credential_status(config: LLMConfig) -> str:
    return "redacted" if config.has_api_key else "not_configured"


def _provenance(
    config: LLMConfig,
    *,
    input_context_hash: str,
    network_call_performed: bool,
    output_validation_status: str,
    safety_check_status: str,
) -> LlmReportProvenance:
    return LlmReportProvenance(
        provider=config.provider,
        model=config.model,
        base_url_status="configured" if config.base_url else "not_configured",
        credential_status=credential_status(config),
        network_call_performed=network_call_performed,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        input_context_hash=input_context_hash,
        output_validation_status=output_validation_status,
        safety_check_status=safety_check_status,
    )


def _status_report(
    *,
    status: str,
    config: LLMConfig,
    provenance: LlmReportProvenance,
    executive_summary: str,
    scenario_reading: str,
    language: str,
    raw_text_preview: str | None = None,
) -> LlmScenarioReport:
    return LlmScenarioReport(
        status=status,
        provider=config.provider,
        model=config.model,
        language=language,
        executive_summary=executive_summary,
        scenario_reading=scenario_reading,
        daily_highlights=[],
        agent_interpretations=[],
        risk_themes=[],
        caveats=[_default_caveat(language)],
        disclaimer=_default_disclaimer(language),
        raw_text_preview=raw_text_preview,
        provenance=provenance,
    )


def _default_disclaimer(language: str) -> str:
    if language == "zh-Hant":
        return "僅為相關性分析；僅為情境推演；不構成財務建議；不是交易訊號。"
    return "association only; scenario rehearsal only; not financial advice; not a trading signal."


def _default_caveat(language: str) -> str:
    if language == "zh-Hant":
        return "LLM 報告只解釋既有情境脈絡，不是市場資料來源。"
    return "LLM report explains existing scenario context only; it is not a market data source."


def _preview(raw_text: str) -> str:
    return raw_text[:RAW_TEXT_PREVIEW_LIMIT]


def _daily_highlights_from_payload(value: Any) -> list[LlmDailyHighlight]:
    highlights: list[LlmDailyHighlight] = []
    if not isinstance(value, list):
        return highlights
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = {
            "date": item.get("date"),
            "summary": str(item.get("summary") or ""),
            "key_context": _string_list(item.get("key_context", [])),
            "agent_focus": _string_list(item.get("agent_focus", [])),
            "caveats": _string_list(item.get("caveats", [])),
        }
        try:
            highlights.append(LlmDailyHighlight.model_validate(normalized))
        except ValueError:
            continue
    return highlights


def _agent_interpretations_from_payload(value: Any) -> list[LlmAgentInterpretation]:
    interpretations: list[LlmAgentInterpretation] = []
    if not isinstance(value, list):
        return interpretations
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = {
            "agent_id": str(item.get("agent_id") or ""),
            "agent_name": str(item.get("agent_name") or ""),
            "interpretation": str(item.get("interpretation") or ""),
            "risk_focus": _string_list(item.get("risk_focus", [])),
            "caveats": _string_list(item.get("caveats", [])),
        }
        try:
            interpretations.append(LlmAgentInterpretation.model_validate(normalized))
        except ValueError:
            continue
    return interpretations


def _asset_stress_indicators_from_payload(value: Any) -> list[LlmAssetStressIndicator]:
    indicators: list[LlmAssetStressIndicator] = []
    if not isinstance(value, list):
        return indicators
    for item in value:
        if not isinstance(item, dict):
            continue
        score = _stress_support_score(item)
        if score is None:
            continue
        normalized = {
            "date": item.get("date"),
            "asset": str(item.get("asset") or "").strip().upper(),
            "sentiment_stress_support": score,
            "label": _stress_support_label(str(item.get("label") or ""), score),
            "rationale": str(item.get("rationale") or ""),
            "caveats": _string_list(item.get("caveats", [])),
        }
        try:
            indicators.append(LlmAssetStressIndicator.model_validate(normalized))
        except ValueError:
            continue
    return indicators


def _stress_support_score(item: dict[str, Any]) -> float | None:
    candidates = (
        item.get("sentiment_stress_support"),
        item.get("stress_support"),
        item.get("value"),
        item.get("score"),
    )
    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            return max(0.0, min(100.0, float(candidate)))
        if isinstance(candidate, str) and candidate.strip():
            try:
                return max(0.0, min(100.0, float(candidate)))
            except ValueError:
                continue
    return None


def _stress_support_label(value: str, score: float) -> str:
    label = value.strip().lower().replace(" ", "_").replace("-", "_")
    if label in {"low_support", "mid_support", "high_support"}:
        return label
    if score <= 35:
        return "low_support"
    if score >= 66:
        return "high_support"
    return "mid_support"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _merge_string_lists(left: list[str], right: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*left, *right]:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def _date_range(start: date, end: date) -> set[date]:
    days: set[date] = set()
    current = start
    while current <= end:
        days.add(current)
        current += timedelta(days=1)
    return days


def _timeout_seconds(value: float | None = None) -> float:
    if value is not None:
        return max(1.0, float(value))
    raw = os.getenv(LLM_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _max_output_tokens(value: int | None = None) -> int:
    if value is not None:
        return max(512, int(value))
    raw = os.getenv(LLM_MAX_OUTPUT_TOKENS_ENV)
    if not raw:
        return DEFAULT_MAX_OUTPUT_TOKENS
    try:
        return max(512, int(raw))
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS
