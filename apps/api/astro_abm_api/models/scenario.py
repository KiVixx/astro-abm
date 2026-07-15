from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from astro_abm_api.models.llm import LLMProvider


Visibility = Literal["private", "public"]
ScenarioMode = Literal["daily_association_only"]
ReportLanguage = Literal["en", "zh-Hant"]
WorldlineProvider = Literal["deterministic_mock", "llm"]
WorldlineChunkDays = Literal[1, 2, 3, 5]


class ScenarioCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str | None = None
    start_date: date
    end_date: date
    assets: list[str] = Field(min_length=1)
    agent_ids: list[str] = Field(min_length=1)
    llm_provider: LLMProvider = "mock"
    llm_preset_id: str | None = None
    llm_real_enabled: bool | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = Field(default=None, exclude=True, repr=False)
    llm_user_prompt: str | None = Field(default=None, max_length=4000)
    llm_timeout_seconds: float | None = Field(default=None, ge=1, le=600)
    llm_max_output_tokens: int | None = Field(default=None, ge=512, le=32000)
    llm_call_delay_seconds: float | None = Field(default=None, ge=0, le=120)
    visibility: Visibility = "private"
    mode: ScenarioMode = "daily_association_only"
    language: ReportLanguage = "en"
    worldline_provider: WorldlineProvider = "deterministic_mock"
    worldline_chunk_days: WorldlineChunkDays = 3

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()

    @field_validator("assets", "agent_ids")
    @classmethod
    def values_must_not_be_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("list must not be empty")
        return cleaned

    @field_validator("llm_base_url", "llm_model", "llm_api_key", "llm_user_prompt")
    @classmethod
    def optional_strings_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def date_range_must_be_ordered(self) -> "ScenarioCreateRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        return self


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    title: str
    description: str | None = None
    created_at: datetime
    start_date: date
    end_date: date
    assets: list[str]
    agent_ids: list[str]
    agent_names: list[str]
    visibility: Visibility
    mode: ScenarioMode
    language: ReportLanguage | None = None


class ScenarioLlmChunkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_provider: LLMProvider = "openai_compatible"
    llm_preset_id: str | None = None
    llm_real_enabled: bool | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = Field(default=None, exclude=True, repr=False)
    llm_user_prompt: str | None = Field(default=None, max_length=4000)
    llm_timeout_seconds: float | None = Field(default=None, ge=1, le=600)
    llm_max_output_tokens: int | None = Field(default=None, ge=512, le=32000)
    llm_call_delay_seconds: float | None = Field(default=None, ge=0, le=120)
    language: ReportLanguage = "en"
    chunk_start_date: date
    chunk_end_date: date
    chunk_index: int = Field(ge=1)
    total_chunks: int = Field(ge=1)

    @field_validator("llm_base_url", "llm_model", "llm_api_key", "llm_user_prompt")
    @classmethod
    def optional_strings_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def chunk_date_range_must_be_ordered(self) -> "ScenarioLlmChunkRequest":
        if self.chunk_start_date > self.chunk_end_date:
            raise ValueError("chunk_start_date must be <= chunk_end_date")
        if self.chunk_index > self.total_chunks:
            raise ValueError("chunk_index must be <= total_chunks")
        return self


class ScenarioWorldlineChunkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_provider: LLMProvider = "openai_compatible"
    llm_preset_id: str | None = None
    llm_real_enabled: bool | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = Field(default=None, exclude=True, repr=False)
    llm_user_prompt: str | None = Field(default=None, max_length=4000)
    llm_timeout_seconds: float | None = Field(default=None, ge=1, le=600)
    llm_max_output_tokens: int | None = Field(default=None, ge=512, le=32000)
    llm_call_delay_seconds: float | None = Field(default=None, ge=0, le=120)
    language: ReportLanguage = "en"
    chunk_start_date: date
    chunk_end_date: date
    chunk_index: int = Field(ge=1)
    total_chunks: int = Field(ge=1)
    worldline_chunk_days: WorldlineChunkDays = 3

    @field_validator("llm_base_url", "llm_model", "llm_api_key", "llm_user_prompt")
    @classmethod
    def optional_strings_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def chunk_date_range_must_be_ordered(self) -> "ScenarioWorldlineChunkRequest":
        if self.chunk_start_date > self.chunk_end_date:
            raise ValueError("chunk_start_date must be <= chunk_end_date")
        if self.chunk_index > self.total_chunks:
            raise ValueError("chunk_index must be <= total_chunks")
        return self
