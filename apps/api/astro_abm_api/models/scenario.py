from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from astro_abm_api.models.llm import LLMProvider


Visibility = Literal["private", "public"]
ScenarioMode = Literal["daily_association_only"]
ReportLanguage = Literal["en", "zh-Hant"]


class ScenarioCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str | None = None
    start_date: date
    end_date: date
    assets: list[str] = Field(min_length=1)
    agent_ids: list[str] = Field(min_length=1)
    llm_provider: LLMProvider = "mock"
    llm_base_url: str | None = None
    llm_model: str | None = None
    visibility: Visibility = "private"
    mode: ScenarioMode = "daily_association_only"
    language: ReportLanguage = "en"

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
