from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


LLMProvider = Literal["mock", "openai_compatible"]


class LLMTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: LLMProvider = "mock"
    real_enabled: bool | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    timeout_seconds: float | None = None
    max_output_tokens: int | None = None


class LLMTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: LLMProvider
    reachable: bool
    dry_run: bool
    status: str = "ok"
    message: str
    base_url: str | None = None
    model: str | None = None
