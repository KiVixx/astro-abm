from __future__ import annotations

import os
from dataclasses import dataclass

from astro_abm_api.models.llm import LLMProvider, LLMTestRequest, LLMTestResponse


LLM_API_KEY_ENV = "ASTRO_ABM_LLM_API_KEY"
LLM_BASE_URL_ENV = "ASTRO_ABM_LLM_BASE_URL"
LLM_MODEL_ENV = "ASTRO_ABM_LLM_MODEL"


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider = "mock"
    base_url: str | None = None
    model: str | None = None
    has_api_key: bool = False


def build_llm_config(
    provider: LLMProvider = "mock",
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    resolved_base_url = base_url or os.getenv(LLM_BASE_URL_ENV)
    resolved_model = model or os.getenv(LLM_MODEL_ENV)
    has_api_key = bool(api_key or os.getenv(LLM_API_KEY_ENV))
    return LLMConfig(
        provider=provider,
        base_url=resolved_base_url,
        model=resolved_model,
        has_api_key=has_api_key,
    )


def provenance_for_llm(config: LLMConfig) -> dict[str, object]:
    return {
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "credential_status": "redacted" if config.has_api_key else "not_configured",
        "network_call_performed": False,
    }


def test_llm_connection(request: LLMTestRequest) -> LLMTestResponse:
    config = build_llm_config(
        provider=request.provider,
        base_url=request.base_url,
        model=request.model,
        api_key=request.api_key,
    )
    if config.provider == "mock":
        return LLMTestResponse(
            provider="mock",
            reachable=True,
            dry_run=True,
            message="Mock LLM provider is available. No network call was made.",
            base_url=None,
            model="mock-deterministic",
        )

    if not config.base_url or not config.model:
        return LLMTestResponse(
            provider="openai_compatible",
            reachable=False,
            dry_run=True,
            message="OpenAI-compatible provider is not configured. Provide base_url and model.",
            base_url=config.base_url,
            model=config.model,
        )

    return LLMTestResponse(
        provider="openai_compatible",
        reachable=True,
        dry_run=True,
        message="OpenAI-compatible provider configuration is present. PR1 does not perform network calls.",
        base_url=config.base_url,
        model=config.model,
    )
