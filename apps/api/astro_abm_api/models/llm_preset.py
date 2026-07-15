from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from astro_abm_api.models.llm import LLMProvider


class LlmPresetSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    provider: LLMProvider = "openai_compatible"
    real_enabled: bool = True
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = Field(default=None, exclude=True, repr=False)
    keep_existing_api_key: bool = True
    worldline_provider: str = "llm"
    chunk_size_days: int = Field(default=3, ge=1, le=5)
    call_delay_seconds: float = Field(default=2, ge=0, le=120)
    timeout_seconds: float = Field(default=120, ge=1, le=600)
    max_output_tokens: int = Field(default=5000, ge=512, le=32000)
    custom_user_prompt: str | None = Field(default=None, max_length=4000)
    default_language: str = "zh-Hant"

    @field_validator("name", "base_url", "model", "api_key", "custom_user_prompt")
    @classmethod
    def clean_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LlmPresetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    name: str
    provider: LLMProvider
    real_enabled: bool
    base_url: str | None
    model: str | None
    has_api_key: bool
    worldline_provider: str
    chunk_size_days: int
    call_delay_seconds: float
    timeout_seconds: float
    max_output_tokens: int
    custom_user_prompt: str | None
    default_language: str
    created_at: datetime
    updated_at: datetime


class LlmPresetTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    reachable: bool
    dry_run: bool
    status: str
    message: str
    provider: LLMProvider
    model: str | None
    credential_status: str
