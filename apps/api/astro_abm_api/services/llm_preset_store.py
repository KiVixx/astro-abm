from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from astro_abm_api.models.llm_preset import LlmPresetSaveRequest, LlmPresetSummary
from astro_abm_api.services.scenario_store import repo_root


LOCAL_CONFIG_DIR_ENV = "ASTRO_ABM_LOCAL_CONFIG_DIR"
PRESET_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
_LOCK = threading.RLock()


class LlmPresetNotFoundError(KeyError):
    pass


def default_local_config_dir() -> Path:
    configured = os.getenv(LOCAL_CONFIG_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return repo_root() / ".local" / "astro-abm"


class LlmPresetStore:
    def __init__(self, config_dir: Path | str | None = None) -> None:
        self.config_dir = (
            Path(config_dir).expanduser().resolve()
            if config_dir
            else default_local_config_dir()
        )
        self.path = self.config_dir / "llm_presets.json"

    def list(self) -> list[LlmPresetSummary]:
        records = self._read_records()
        return sorted(
            (self._summary(record) for record in records.values()),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def get_summary(self, preset_id: str) -> LlmPresetSummary:
        return self._summary(self.get_record(preset_id))

    def get_record(self, preset_id: str) -> dict[str, Any]:
        self._validate_id(preset_id)
        record = self._read_records().get(preset_id)
        if record is None:
            raise LlmPresetNotFoundError(preset_id)
        return dict(record)

    def create(self, request: LlmPresetSaveRequest) -> LlmPresetSummary:
        with _LOCK:
            records = self._read_records()
            preset_id = self._new_id(request.name, records)
            now = datetime.now(UTC).isoformat()
            records[preset_id] = self._record_from_request(
                preset_id, request, created_at=now, api_key=request.api_key
            )
            self._write_records(records)
            return self._summary(records[preset_id])

    def update(self, preset_id: str, request: LlmPresetSaveRequest) -> LlmPresetSummary:
        self._validate_id(preset_id)
        with _LOCK:
            records = self._read_records()
            existing = records.get(preset_id)
            if existing is None:
                raise LlmPresetNotFoundError(preset_id)
            api_key = request.api_key
            if api_key is None and request.keep_existing_api_key:
                api_key = existing.get("api_key")
            records[preset_id] = self._record_from_request(
                preset_id,
                request,
                created_at=str(existing["created_at"]),
                api_key=api_key,
            )
            self._write_records(records)
            return self._summary(records[preset_id])

    def delete(self, preset_id: str) -> None:
        self._validate_id(preset_id)
        with _LOCK:
            records = self._read_records()
            if preset_id not in records:
                raise LlmPresetNotFoundError(preset_id)
            del records[preset_id]
            self._write_records(records)

    def _read_records(self) -> dict[str, dict[str, Any]]:
        with _LOCK:
            if not self.path.exists():
                return {}
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("local LLM preset store is unreadable") from exc
            records = payload.get("presets") if isinstance(payload, dict) else None
            if not isinstance(records, dict):
                raise ValueError("local LLM preset store has an invalid schema")
            return {
                key: value
                for key, value in records.items()
                if isinstance(key, str) and isinstance(value, dict)
            }

    def _write_records(self, records: dict[str, dict[str, Any]]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {"version": 1, "presets": records}
        fd, temp_name = tempfile.mkstemp(
            prefix="llm_presets_", suffix=".json", dir=self.config_dir
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _validate_id(preset_id: str) -> None:
        if not PRESET_ID_PATTERN.fullmatch(preset_id):
            raise ValueError("preset_id contains invalid characters")

    @staticmethod
    def _new_id(name: str, records: dict[str, Any]) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "preset"
        while True:
            candidate = f"{slug}_{uuid4().hex[:8]}"
            if candidate not in records:
                return candidate

    @staticmethod
    def _record_from_request(
        preset_id: str,
        request: LlmPresetSaveRequest,
        *,
        created_at: str,
        api_key: str | None,
    ) -> dict[str, Any]:
        return {
            "preset_id": preset_id,
            "name": request.name,
            "provider": request.provider,
            "real_enabled": request.real_enabled,
            "base_url": request.base_url,
            "model": request.model,
            "api_key": api_key,
            "worldline_provider": request.worldline_provider,
            "chunk_size_days": request.chunk_size_days,
            "call_delay_seconds": request.call_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
            "max_output_tokens": request.max_output_tokens,
            "custom_user_prompt": request.custom_user_prompt,
            "default_language": request.default_language,
            "created_at": created_at,
            "updated_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _summary(record: dict[str, Any]) -> LlmPresetSummary:
        return LlmPresetSummary(
            preset_id=str(record["preset_id"]),
            name=str(record["name"]),
            provider=record.get("provider", "openai_compatible"),
            real_enabled=bool(record.get("real_enabled", True)),
            base_url=record.get("base_url"),
            model=record.get("model"),
            has_api_key=bool(record.get("api_key")),
            worldline_provider=str(record.get("worldline_provider", "llm")),
            chunk_size_days=int(record.get("chunk_size_days", 1)),
            call_delay_seconds=float(record.get("call_delay_seconds", 6)),
            timeout_seconds=float(record.get("timeout_seconds", 120)),
            max_output_tokens=int(record.get("max_output_tokens", 32000)),
            custom_user_prompt=record.get("custom_user_prompt"),
            default_language=str(record.get("default_language", "zh-Hant")),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )
