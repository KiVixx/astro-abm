from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScenarioExportEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    exported_at: datetime
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    report: dict[str, Any]
    notes: list[str]


class ScenarioImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envelope: ScenarioExportEnvelope
    visibility: str | None = Field(default=None, pattern=r"^(public|private)$")
